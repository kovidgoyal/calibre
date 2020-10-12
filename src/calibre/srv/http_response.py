#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, hashlib, uuid, struct
from collections import namedtuple
from io import BytesIO, DEFAULT_BUFFER_SIZE
from itertools import chain, repeat
from operator import itemgetter
from functools import wraps

from polyglot.builtins import iteritems, itervalues, reraise, map, unicode_type, string_or_bytes

from calibre import guess_type, force_unicode
from calibre.constants import __version__
from calibre.srv.loop import WRITE
from calibre.srv.errors import HTTPSimpleResponse
from calibre.srv.http_request import HTTPRequest, read_headers
from calibre.srv.sendfile import file_metadata, sendfile_to_socket_async, CannotSendfile, SendfileInterrupted
from calibre.srv.utils import (
    MultiDict, http_date, HTTP1, HTTP11, socket_errors_socket_closed,
    sort_q_values, get_translator_for_lang, Cookie, fast_now_strftime)
from calibre.utils.speedups import ReadOnlyFileBuffer
from calibre.utils.monotonic import monotonic
from polyglot import http_client, reprlib
from polyglot.builtins import error_message

Range = namedtuple('Range', 'start stop size')
MULTIPART_SEPARATOR = uuid.uuid4().hex
if isinstance(MULTIPART_SEPARATOR, bytes):
    MULTIPART_SEPARATOR = MULTIPART_SEPARATOR.decode('ascii')
COMPRESSIBLE_TYPES = {'application/json', 'application/javascript', 'application/xml', 'application/oebps-package+xml'}
import zlib
from itertools import zip_longest


def header_list_to_file(buf):  # {{{
    buf.append('')
    return ReadOnlyFileBuffer(b''.join((x + '\r\n').encode('ascii') for x in buf))
# }}}


def parse_multipart_byterange(buf, content_type):  # {{{
    sep = (content_type.rsplit('=', 1)[-1]).encode('utf-8')
    ans = []

    def parse_part():
        line = buf.readline()
        if not line:
            raise ValueError('Premature end of message')
        if not line.startswith(b'--' + sep):
            raise ValueError('Malformed start of multipart message: %s' % reprlib.repr(line))
        if line.endswith(b'--'):
            return None
        headers = read_headers(buf.readline)
        cr = headers.get('Content-Range')
        if not cr:
            raise ValueError('Missing Content-Range header in sub-part')
        if not cr.startswith('bytes '):
            raise ValueError('Malformed Content-Range header in sub-part, no prefix')
        try:
            start, stop = map(lambda x: int(x.strip()), cr.partition(' ')[-1].partition('/')[0].partition('-')[::2])
        except Exception:
            raise ValueError('Malformed Content-Range header in sub-part, failed to parse byte range')
        content_length = stop - start + 1
        ret = buf.read(content_length)
        if len(ret) != content_length:
            raise ValueError('Malformed sub-part, length of body not equal to length specified in Content-Range')
        buf.readline()
        return (start, ret)
    while True:
        data = parse_part()
        if data is None:
            break
        ans.append(data)
    return ans
# }}}


def parse_if_none_match(val):  # {{{
    return {x.strip() for x in val.split(',')}
# }}}


def acceptable_encoding(val, allowed=frozenset({'gzip'})):  # {{{
    for x in sort_q_values(val):
        x = x.lower()
        if x in allowed:
            return x
# }}}


def preferred_lang(val, get_translator_for_lang):  # {{{
    for x in sort_q_values(val):
        x = x.lower()
        found, lang, translator = get_translator_for_lang(x)
        if found:
            return x
    return 'en'
# }}}


def get_ranges(headervalue, content_length):  # {{{
    ''' Return a list of ranges from the Range header. If this function returns
    an empty list, it indicates no valid range was found. '''
    if not headervalue:
        return None

    result = []
    try:
        bytesunit, byteranges = headervalue.split("=", 1)
    except Exception:
        return None
    if bytesunit.strip() != 'bytes':
        return None

    for brange in byteranges.split(","):
        start, stop = [x.strip() for x in brange.split("-", 1)]
        if start:
            if not stop:
                stop = content_length - 1
            try:
                start, stop = int(start), int(stop)
            except Exception:
                continue
            if start >= content_length:
                continue
            if stop < start:
                continue
            stop = min(stop, content_length - 1)
            result.append(Range(start, stop, stop - start + 1))
        elif stop:
            # Negative subscript (last N bytes)
            try:
                stop = int(stop)
            except Exception:
                continue
            if stop > content_length:
                result.append(Range(0, content_length-1, content_length))
            else:
                result.append(Range(content_length - stop, content_length - 1, stop))

    return result
# }}}

# gzip transfer encoding  {{{


def gzip_prefix():
    # See http://www.gzip.org/zlib/rfc-gzip.html
    return b''.join((
        b'\x1f\x8b',       # ID1 and ID2: gzip marker
        b'\x08',           # CM: compression method
        b'\x00',           # FLG: none set
        # MTIME: 4 bytes, set to zero so as not to leak timezone information
        b'\0\0\0\0',
        b'\x02',           # XFL: max compression, slowest algo
        b'\xff',           # OS: unknown
    ))


def compress_readable_output(src_file, compress_level=6):
    crc = zlib.crc32(b"")
    size = 0
    zobj = zlib.compressobj(compress_level,
                            zlib.DEFLATED, -zlib.MAX_WBITS,
                            zlib.DEF_MEM_LEVEL, zlib.Z_DEFAULT_STRATEGY)
    prefix_written = False
    while True:
        data = src_file.read(DEFAULT_BUFFER_SIZE)
        if not data:
            break
        size += len(data)
        crc = zlib.crc32(data, crc)
        data = zobj.compress(data)
        if not prefix_written:
            prefix_written = True
            data = gzip_prefix() + data
        yield data
    yield zobj.flush() + struct.pack(b"<L", crc & 0xffffffff) + struct.pack(b"<L", size)
# }}}


def get_range_parts(ranges, content_type, content_length):  # {{{

    def part(r):
        ans = ['--%s' % MULTIPART_SEPARATOR, 'Content-Range: bytes %d-%d/%d' % (r.start, r.stop, content_length)]
        if content_type:
            ans.append('Content-Type: %s' % content_type)
        ans.append('')
        return ('\r\n'.join(ans)).encode('ascii')
    return list(map(part, ranges)) + [('--%s--' % MULTIPART_SEPARATOR).encode('ascii')]
# }}}


class ETaggedFile(object):  # {{{

    def __init__(self, output, etag):
        self.output, self.etag = output, etag

    def fileno(self):
        return self.output.fileno()
# }}}


class RequestData(object):  # {{{

    cookies = {}
    username = None

    def __init__(self, method, path, query, inheaders, request_body_file, outheaders, response_protocol,
                 static_cache, opts, remote_addr, remote_port, is_trusted_ip, translator_cache,
                 tdir, forwarded_for, request_original_uri=None):

        (self.method, self.path, self.query, self.inheaders, self.request_body_file, self.outheaders,
         self.response_protocol, self.static_cache, self.translator_cache) = (
            method, path, query, inheaders, request_body_file, outheaders,
            response_protocol, static_cache, translator_cache
        )

        self.remote_addr, self.remote_port, self.is_trusted_ip = remote_addr, remote_port, is_trusted_ip
        self.forwarded_for = forwarded_for
        self.request_original_uri = request_original_uri
        self.opts = opts
        self.status_code = http_client.OK
        self.outcookie = Cookie()
        self.lang_code = self.gettext_func = self.ngettext_func = None
        self.set_translator(self.get_preferred_language())
        self.tdir = tdir

    def generate_static_output(self, name, generator, content_type='text/html; charset=UTF-8'):
        ans = self.static_cache.get(name)
        if ans is None:
            ans = self.static_cache[name] = StaticOutput(generator())
        ct = self.outheaders.get('Content-Type')
        if not ct:
            self.outheaders.set('Content-Type', content_type, replace_all=True)
        return ans

    def filesystem_file_with_custom_etag(self, output, *etag_parts):
        etag = hashlib.sha1()
        tuple(map(lambda x:etag.update(unicode_type(x).encode('utf-8')), etag_parts))
        return ETaggedFile(output, etag.hexdigest())

    def filesystem_file_with_constant_etag(self, output, etag_as_hexencoded_string):
        return ETaggedFile(output, etag_as_hexencoded_string)

    def etagged_dynamic_response(self, etag, func, content_type='text/html; charset=UTF-8'):
        ' A response that is generated only if the etag does not match '
        ct = self.outheaders.get('Content-Type')
        if not ct:
            self.outheaders.set('Content-Type', content_type, replace_all=True)
        if not etag.endswith('"'):
            etag = '"%s"' % etag
        return ETaggedDynamicOutput(func, etag)

    def read(self, size=-1):
        return self.request_body_file.read(size)

    def peek(self, size=-1):
        pos = self.request_body_file.tell()
        try:
            return self.read(size)
        finally:
            self.request_body_file.seek(pos)

    def get_translator(self, bcp_47_code):
        return get_translator_for_lang(self.translator_cache, bcp_47_code)

    def get_preferred_language(self):
        return preferred_lang(self.inheaders.get('Accept-Language'), self.get_translator)

    def _(self, text):
        return self.gettext_func(text)

    def ngettext(self, singular, plural, n):
        return self.ngettext_func(singular, plural, n)

    def set_translator(self, lang_code):
        if lang_code != self.lang_code:
            found, lang, t = self.get_translator(lang_code)
            self.lang_code = lang
            self.gettext_func = t.gettext
            self.ngettext_func = t.ngettext
# }}}


class ReadableOutput(object):

    def __init__(self, output, etag=None, content_length=None):
        self.src_file = output
        if content_length is None:
            self.src_file.seek(0, os.SEEK_END)
            self.content_length = self.src_file.tell()
        else:
            self.content_length = content_length
        self.etag = etag
        self.accept_ranges = True
        self.use_sendfile = False
        self.src_file.seek(0)


def filesystem_file_output(output, outheaders, stat_result):
    etag = getattr(output, 'etag', None)
    if etag is None:
        oname = output.name or ''
        if not isinstance(oname, string_or_bytes):
            oname = unicode_type(oname)
        etag = hashlib.sha1((unicode_type(stat_result.st_mtime) + force_unicode(oname)).encode('utf-8')).hexdigest()
    else:
        output = output.output
    etag = '"%s"' % etag
    self = ReadableOutput(output, etag=etag, content_length=stat_result.st_size)
    self.name = output.name
    self.use_sendfile = True
    return self


def dynamic_output(output, outheaders, etag=None):
    if isinstance(output, bytes):
        data = output
    else:
        data = output.encode('utf-8')
        ct = outheaders.get('Content-Type')
        if not ct:
            outheaders.set('Content-Type', 'text/plain; charset=UTF-8', replace_all=True)
    ans = ReadableOutput(ReadOnlyFileBuffer(data), etag=etag)
    ans.accept_ranges = False
    return ans


class ETaggedDynamicOutput(object):

    def __init__(self, func, etag):
        self.func, self.etag = func, etag

    def __call__(self):
        return self.func()


class GeneratedOutput(object):

    def __init__(self, output, etag=None):
        self.output = output
        self.content_length = None
        self.etag = etag
        self.accept_ranges = False


class StaticOutput(object):

    def __init__(self, data):
        if isinstance(data, unicode_type):
            data = data.encode('utf-8')
        self.data = data
        self.etag = '"%s"' % hashlib.sha1(data).hexdigest()
        self.content_length = len(data)


class HTTPConnection(HTTPRequest):

    use_sendfile = False

    def write(self, buf, end=None):
        pos = buf.tell()
        if end is None:
            buf.seek(0, os.SEEK_END)
            end = buf.tell()
            buf.seek(pos)
        limit = end - pos
        if limit <= 0:
            return True
        if self.use_sendfile and not isinstance(buf, (BytesIO, ReadOnlyFileBuffer)):
            try:
                sent = sendfile_to_socket_async(buf, pos, limit, self.socket)
            except CannotSendfile:
                self.use_sendfile = False
                return False
            except SendfileInterrupted:
                return False
            except IOError as e:
                if e.errno in socket_errors_socket_closed:
                    self.ready = self.use_sendfile = False
                    return False
                raise
            finally:
                self.last_activity = monotonic()
            if sent == 0:
                # Something bad happened, was the file modified on disk by
                # another process?
                self.use_sendfile = self.ready = False
                raise IOError('sendfile() failed to write any bytes to the socket')
        else:
            data = buf.read(min(limit, self.send_bufsize))
            sent = self.send(data)
        buf.seek(pos + sent)
        return buf.tell() >= end

    def simple_response(self, status_code, msg='', close_after_response=True, extra_headers=None):
        if self.response_protocol is HTTP1:
            # HTTP/1.0 has no 413/414/303 codes
            status_code = {
                http_client.REQUEST_ENTITY_TOO_LARGE:http_client.BAD_REQUEST,
                http_client.REQUEST_URI_TOO_LONG:http_client.BAD_REQUEST,
                http_client.SEE_OTHER:http_client.FOUND
            }.get(status_code, status_code)

        self.close_after_response = close_after_response
        msg = msg.encode('utf-8')
        ct = 'http' if self.method == 'TRACE' else 'plain'
        buf = [
            '%s %d %s' % (self.response_protocol, status_code, http_client.responses[status_code]),
            "Content-Length: %s" % len(msg),
            "Content-Type: text/%s; charset=UTF-8" % ct,
            "Date: " + http_date(),
        ]
        if self.close_after_response and self.response_protocol is HTTP11:
            buf.append("Connection: close")
        if extra_headers is not None:
            for h, v in iteritems(extra_headers):
                buf.append('%s: %s' % (h, v))
        buf.append('')
        buf = [(x + '\r\n').encode('ascii') for x in buf]
        if self.method != 'HEAD':
            buf.append(msg)
        response_data = b''.join(buf)
        self.log_access(status_code=status_code, response_size=len(response_data))
        self.response_ready(ReadOnlyFileBuffer(response_data))

    def prepare_response(self, inheaders, request_body_file):
        if self.method == 'TRACE':
            msg = force_unicode(self.request_line, 'utf-8') + '\n' + inheaders.pretty()
            return self.simple_response(http_client.OK, msg, close_after_response=False)
        request_body_file.seek(0)
        outheaders = MultiDict()
        data = RequestData(
            self.method, self.path, self.query, inheaders, request_body_file,
            outheaders, self.response_protocol, self.static_cache, self.opts,
            self.remote_addr, self.remote_port, self.is_trusted_ip,
            self.translator_cache, self.tdir, self.forwarded_for, self.request_original_uri
        )
        self.queue_job(self.run_request_handler, data)

    def run_request_handler(self, data):
        result = self.request_handler(data)
        return data, result

    def send_range_not_satisfiable(self, content_length):
        buf = [
            '%s %d %s' % (
                self.response_protocol,
                http_client.REQUESTED_RANGE_NOT_SATISFIABLE,
                http_client.responses[http_client.REQUESTED_RANGE_NOT_SATISFIABLE]),
            "Date: " + http_date(),
            "Content-Range: bytes */%d" % content_length,
        ]
        response_data = header_list_to_file(buf)
        self.log_access(status_code=http_client.REQUESTED_RANGE_NOT_SATISFIABLE, response_size=response_data.sz)
        self.response_ready(response_data)

    def send_not_modified(self, etag=None):
        buf = [
            '%s %d %s' % (self.response_protocol, http_client.NOT_MODIFIED, http_client.responses[http_client.NOT_MODIFIED]),
            "Content-Length: 0",
            "Date: " + http_date(),
        ]
        if etag is not None:
            buf.append('ETag: ' + etag)
        response_data = header_list_to_file(buf)
        self.log_access(status_code=http_client.NOT_MODIFIED, response_size=response_data.sz)
        self.response_ready(response_data)

    def report_busy(self):
        self.simple_response(http_client.SERVICE_UNAVAILABLE)

    def job_done(self, ok, result):
        if not ok:
            etype, e, tb = result
            if isinstance(e, HTTPSimpleResponse):
                eh = {}
                if e.location:
                    eh['Location'] = e.location
                if e.authenticate:
                    eh['WWW-Authenticate'] = e.authenticate
                if e.log:
                    self.log.warn(e.log)
                return self.simple_response(e.http_code, msg=error_message(e) or '', close_after_response=e.close_connection, extra_headers=eh)
            reraise(etype, e, tb)

        data, output = result
        output = self.finalize_output(output, data, self.method is HTTP1)
        if output is None:
            return
        outheaders = data.outheaders

        outheaders.set('Date', http_date(), replace_all=True)
        outheaders.set('Server', 'calibre %s' % __version__, replace_all=True)
        keep_alive = not self.close_after_response and self.opts.timeout > 0
        if keep_alive:
            outheaders.set('Keep-Alive', 'timeout=%d' % int(self.opts.timeout))
        if 'Connection' not in outheaders:
            if self.response_protocol is HTTP11:
                if self.close_after_response:
                    outheaders.set('Connection', 'close')
            else:
                if not self.close_after_response:
                    outheaders.set('Connection', 'Keep-Alive')

        ct = outheaders.get('Content-Type', '')
        if ct.startswith('text/') and 'charset=' not in ct:
            outheaders.set('Content-Type', ct + '; charset=UTF-8', replace_all=True)

        buf = [HTTP11 + (' %d ' % data.status_code) + http_client.responses[data.status_code]]
        for header, value in sorted(iteritems(outheaders), key=itemgetter(0)):
            buf.append('%s: %s' % (header, value))
        for morsel in itervalues(data.outcookie):
            morsel['version'] = '1'
            x = morsel.output()
            if isinstance(x, bytes):
                x = x.decode('ascii')
            buf.append(x)
        buf.append('')
        response_data = ReadOnlyFileBuffer(b''.join((x + '\r\n').encode('ascii') for x in buf))
        if self.access_log is not None:
            sz = outheaders.get('Content-Length')
            if sz is not None:
                sz = int(sz) + response_data.sz
            self.log_access(status_code=data.status_code, response_size=sz, username=data.username)
        self.response_ready(response_data, output=output)

    def log_access(self, status_code, response_size=None, username=None):
        if self.access_log is None:
            return
        if not self.opts.log_not_found and status_code == http_client.NOT_FOUND:
            return
        ff = self.forwarded_for
        if ff:
            ff = '[%s] ' % ff
        line = '%s port-%s %s%s %s "%s" %s %s' % (
            self.remote_addr, self.remote_port, ff or '', username or '-',
            fast_now_strftime('%d/%b/%Y:%H:%M:%S %z'),
            force_unicode(self.request_line or '', 'utf-8'),
            status_code, ('-' if response_size is None else response_size))
        self.access_log(line)

    def response_ready(self, header_file, output=None):
        self.response_started = True
        self.optimize_for_sending_packet()
        self.use_sendfile = False
        self.set_state(WRITE, self.write_response_headers, header_file, output)

    def write_response_headers(self, buf, output, event):
        if self.write(buf):
            self.write_response_body(output)

    def write_response_body(self, output):
        if output is None or self.method == 'HEAD':
            self.reset_state()
            return
        if isinstance(output, ReadableOutput):
            self.use_sendfile = output.use_sendfile and self.opts.use_sendfile and sendfile_to_socket_async is not None and self.ssl_context is None
            # sendfile() does not work with SSL sockets since encryption has to
            # be done in userspace
            if output.ranges is not None:
                if isinstance(output.ranges, Range):
                    r = output.ranges
                    output.src_file.seek(r.start)
                    self.set_state(WRITE, self.write_buf, output.src_file, end=r.stop + 1)
                else:
                    self.set_state(WRITE, self.write_ranges, output.src_file, output.ranges, first=True)
            else:
                self.set_state(WRITE, self.write_buf, output.src_file)
        elif isinstance(output, GeneratedOutput):
            self.set_state(WRITE, self.write_iter, chain(output.output, repeat(None, 1)))
        else:
            raise TypeError('Unknown output type: %r' % output)

    def write_buf(self, buf, event, end=None):
        if self.write(buf, end=end):
            self.reset_state()

    def write_ranges(self, buf, ranges, event, first=False):
        r, range_part = next(ranges)
        if r is None:
            # EOF range part
            self.set_state(WRITE, self.write_buf, ReadOnlyFileBuffer(b'\r\n' + range_part))
        else:
            buf.seek(r.start)
            self.set_state(WRITE, self.write_range_part, ReadOnlyFileBuffer((b'' if first else b'\r\n') + range_part + b'\r\n'), buf, r.stop + 1, ranges)

    def write_range_part(self, part_buf, buf, end, ranges, event):
        if self.write(part_buf):
            self.set_state(WRITE, self.write_range, buf, end, ranges)

    def write_range(self, buf, end, ranges, event):
        if self.write(buf, end=end):
            self.set_state(WRITE, self.write_ranges, buf, ranges)

    def write_iter(self, output, event):
        chunk = next(output)
        if chunk is None:
            self.set_state(WRITE, self.write_chunk, ReadOnlyFileBuffer(b'0\r\n\r\n'), output, last=True)
        else:
            if chunk:
                if not isinstance(chunk, bytes):
                    chunk = chunk.encode('utf-8')
                chunk = ('%X\r\n' % len(chunk)).encode('ascii') + chunk + b'\r\n'
                self.set_state(WRITE, self.write_chunk, ReadOnlyFileBuffer(chunk), output)
            else:
                # Empty chunk, ignore it
                self.write_iter(output, event)

    def write_chunk(self, buf, output, event, last=False):
        if self.write(buf):
            if last:
                self.reset_state()
            else:
                self.set_state(WRITE, self.write_iter, output)

    def reset_state(self):
        ready = not self.close_after_response
        self.end_send_optimization()
        self.connection_ready()
        self.ready = ready

    def report_unhandled_exception(self, e, formatted_traceback):
        self.simple_response(http_client.INTERNAL_SERVER_ERROR)

    def finalize_output(self, output, request, is_http1):
        none_match = parse_if_none_match(request.inheaders.get('If-None-Match', ''))
        if isinstance(output, ETaggedDynamicOutput):
            matched = '*' in none_match or (output.etag and output.etag in none_match)
            if matched:
                if self.method in ('GET', 'HEAD'):
                    self.send_not_modified(output.etag)
                else:
                    self.simple_response(http_client.PRECONDITION_FAILED)
                return

        opts = self.opts
        outheaders = request.outheaders
        stat_result = file_metadata(output)
        if stat_result is not None:
            output = filesystem_file_output(output, outheaders, stat_result)
            if 'Content-Type' not in outheaders:
                output_name = output.name
                if not isinstance(output_name, string_or_bytes):
                    output_name = unicode_type(output_name)
                mt = guess_type(output_name)[0]
                if mt:
                    if mt in {'text/plain', 'text/html', 'application/javascript', 'text/css'}:
                        mt += '; charset=UTF-8'
                    outheaders['Content-Type'] = mt
                else:
                    outheaders['Content-Type'] = 'application/octet-stream'
        elif isinstance(output, string_or_bytes):
            output = dynamic_output(output, outheaders)
        elif hasattr(output, 'read'):
            output = ReadableOutput(output)
        elif isinstance(output, StaticOutput):
            output = ReadableOutput(ReadOnlyFileBuffer(output.data), etag=output.etag, content_length=output.content_length)
        elif isinstance(output, ETaggedDynamicOutput):
            output = dynamic_output(output(), outheaders, etag=output.etag)
        else:
            output = GeneratedOutput(output)
        ct = outheaders.get('Content-Type', '').partition(';')[0]
        compressible = (not ct or ct.startswith('text/') or ct.startswith('image/svg') or
                        ct.partition(';')[0] in COMPRESSIBLE_TYPES)
        compressible = (compressible and request.status_code == http_client.OK and
                        (opts.compress_min_size > -1 and output.content_length >= opts.compress_min_size) and
                        acceptable_encoding(request.inheaders.get('Accept-Encoding', '')) and not is_http1)
        accept_ranges = (not compressible and output.accept_ranges is not None and request.status_code == http_client.OK and
                        not is_http1)
        ranges = get_ranges(request.inheaders.get('Range'), output.content_length) if output.accept_ranges and self.method in ('GET', 'HEAD') else None
        if_range = (request.inheaders.get('If-Range') or '').strip()
        if if_range and if_range != output.etag:
            ranges = None
        if ranges is not None and not ranges:
            return self.send_range_not_satisfiable(output.content_length)

        for header in ('Accept-Ranges', 'Content-Encoding', 'Transfer-Encoding', 'ETag', 'Content-Length'):
            outheaders.pop(header, all=True)

        matched = '*' in none_match or (output.etag and output.etag in none_match)
        if matched:
            if self.method in ('GET', 'HEAD'):
                self.send_not_modified(output.etag)
            else:
                self.simple_response(http_client.PRECONDITION_FAILED)
            return

        output.ranges = None

        if output.etag and self.method in ('GET', 'HEAD'):
            outheaders.set('ETag', output.etag, replace_all=True)
        if accept_ranges:
            outheaders.set('Accept-Ranges', 'bytes', replace_all=True)
        if compressible and not ranges:
            outheaders.set('Content-Encoding', 'gzip', replace_all=True)
            if getattr(output, 'content_length', None):
                outheaders.set('Calibre-Uncompressed-Length', '%d' % output.content_length)
            output = GeneratedOutput(compress_readable_output(output.src_file), etag=output.etag)
        if output.content_length is not None and not compressible and not ranges:
            outheaders.set('Content-Length', '%d' % output.content_length, replace_all=True)

        if compressible or output.content_length is None:
            outheaders.set('Transfer-Encoding', 'chunked', replace_all=True)

        if ranges:
            if len(ranges) == 1:
                r = ranges[0]
                outheaders.set('Content-Length', '%d' % r.size, replace_all=True)
                outheaders.set('Content-Range', 'bytes %d-%d/%d' % (r.start, r.stop, output.content_length), replace_all=True)
                output.ranges = r
            else:
                range_parts = get_range_parts(ranges, outheaders.get('Content-Type'), output.content_length)
                size = sum(map(len, range_parts)) + sum(r.size + 4 for r in ranges)
                outheaders.set('Content-Length', '%d' % size, replace_all=True)
                outheaders.set('Content-Type', 'multipart/byteranges; boundary=' + MULTIPART_SEPARATOR, replace_all=True)
                output.ranges = zip_longest(ranges, range_parts)
            request.status_code = http_client.PARTIAL_CONTENT
        return output


def create_http_handler(handler=None, websocket_handler=None):
    from calibre.srv.web_socket import WebSocketConnection
    static_cache = {}
    translator_cache = {}
    if handler is None:
        def dummy_http_handler(data):
            return 'Hello'
        handler = dummy_http_handler

    @wraps(handler)
    def wrapper(*args, **kwargs):
        ans = WebSocketConnection(*args, **kwargs)
        ans.request_handler = handler
        ans.websocket_handler = websocket_handler
        ans.static_cache = static_cache
        ans.translator_cache = translator_cache
        return ans
    return wrapper
