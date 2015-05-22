#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os, hashlib, httplib, zlib, struct, time, uuid
from io import DEFAULT_BUFFER_SIZE, BytesIO
from collections import namedtuple
from functools import partial
from future_builtins import map
from itertools import izip_longest

from calibre import force_unicode, guess_type
from calibre.srv.errors import IfNoneMatch, RangeNotSatisfiable
from calibre.srv.sendfile import file_metadata, copy_range, sendfile_to_socket

Range = namedtuple('Range', 'start stop size')
MULTIPART_SEPARATOR = uuid.uuid4().hex.decode('ascii')

def get_ranges(headervalue, content_length):
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


def acceptable_encoding(val, allowed=frozenset({'gzip'})):
    def enc(x):
        e, r = x.partition(';')[::2]
        p, v = r.partition('=')[::2]
        q = 1.0
        if p == 'q' and v:
            try:
                q = float(v)
            except Exception:
                pass
        return e.lower(), q

    emap = dict(enc(x.strip()) for x in val.split(','))
    acceptable = sorted(set(emap) & allowed, key=emap.__getitem__, reverse=True)
    if acceptable:
        return acceptable[0]

def gzip_prefix(mtime):
    # See http://www.gzip.org/zlib/rfc-gzip.html
    return b''.join((
        b'\x1f\x8b',       # ID1 and ID2: gzip marker
        b'\x08',           # CM: compression method
        b'\x00',           # FLG: none set
        # MTIME: 4 bytes
        struct.pack(b"<L", int(mtime) & 0xFFFFFFFF),
        b'\x02',           # XFL: max compression, slowest algo
        b'\xff',           # OS: unknown
    ))

def write_chunked_data(dest, data):
    dest.write(('%X\r\n' % len(data)).encode('ascii'))
    dest.write(data)
    dest.write(b'\r\n')

def write_compressed_file_obj(input_file, dest, compress_level=6):
    crc = zlib.crc32(b"")
    size = 0
    zobj = zlib.compressobj(compress_level,
                            zlib.DEFLATED, -zlib.MAX_WBITS,
                            zlib.DEF_MEM_LEVEL, 0)
    prefix_written = False
    while True:
        data = input_file.read(DEFAULT_BUFFER_SIZE)
        if not data:
            break
        size += len(data)
        crc = zlib.crc32(data, crc)
        data = zobj.compress(data)
        if not prefix_written:
            prefix_written = True
            data = gzip_prefix(time.time()) + data
        write_chunked_data(dest, data)
    data = zobj.flush() + struct.pack(b"<L", crc & 0xFFFFFFFF) + struct.pack(b"<L", size & 0xFFFFFFFF)
    write_chunked_data(dest, data)
    write_chunked_data(dest, b'')

def get_range_parts(ranges, content_type, content_length):

    def part(r):
        ans = ['--%s' % MULTIPART_SEPARATOR, 'Content-Range: bytes %d-%d/%d' % (r.start, r.stop, content_length)]
        if content_type:
            ans.append('Content-Type: %s' % content_type)
        ans.append('')
        return ('\r\n'.join(ans)).encode('ascii')
    return list(map(part, ranges)) + [('--%s--' % MULTIPART_SEPARATOR).encode('ascii')]

def parse_multipart_byterange(buf, content_type):
    from calibre.srv.http import read_headers
    sep = (content_type.rsplit('=', 1)[-1]).encode('utf-8')
    ans = []

    def parse_part():
        line = buf.readline()
        if not line:
            raise ValueError('Premature end of message')
        if not line.startswith(b'--' + sep):
            raise ValueError('Malformed start of multipart message')
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

class ReadableOutput(object):

    def __init__(self, output, outheaders):
        self.src_file = output
        self.src_file.seek(0, os.SEEK_END)
        self.content_length = self.src_file.tell()
        self.etag = None
        self.accept_ranges = True
        self.use_sendfile = False

    def write(self, dest):
        if self.use_sendfile:
            dest.flush()  # Ensure everything in the SocketFile buffer is sent before calling sendfile()
            sent = sendfile_to_socket(self.src_file, 0, self.content_length, dest)
        else:
            sent = copy_range(self.src_file, 0, self.content_length, dest)
        if sent != self.content_length:
            raise IOError(
                'Failed to send complete file (%r) (%s != %s bytes), perhaps the file was modified during send?' % (
                    getattr(self.src_file, 'name', '<file>'), sent, self.content_length))
        self.src_file = None

    def write_compressed(self, dest):
        self.src_file.seek(0)
        write_compressed_file_obj(self.src_file, dest)
        self.src_file = None

    def write_ranges(self, ranges, dest):
        if isinstance(ranges, Range):
            r = ranges
            self.copy_range(r.start, r.size, dest)
        else:
            for r, header in ranges:
                dest.write(header)
                if r is not None:
                    dest.write(b'\r\n')
                    self.copy_range(r.start, r.size, dest)
                    dest.write(b'\r\n')
        self.src_file = None

    def copy_range(self, start, size, dest):
        if self.use_sendfile:
            dest.flush()  # Ensure everything in the SocketFile buffer is sent before calling sendfile()
            sent = sendfile_to_socket(self.src_file, start, size, dest)
        else:
            sent = copy_range(self.src_file, start, size, dest)
        if sent != size:
            raise IOError('Failed to send byte range from file (%r) (%s != %s bytes), perhaps the file was modified during send?' % (
                    getattr(self.src_file, 'name', '<file>'), sent, size))

class FileSystemOutputFile(ReadableOutput):

    def __init__(self, output, outheaders, stat_result, use_sendfile):
        self.src_file = output
        self.name = output.name
        self.content_length = stat_result.st_size
        self.etag = '"%s"' % hashlib.sha1(type('')(stat_result.st_mtime) + force_unicode(output.name or '')).hexdigest()
        self.accept_ranges = True
        self.use_sendfile = use_sendfile and sendfile_to_socket is not None


class DynamicOutput(object):

    def __init__(self, output, outheaders):
        if isinstance(output, bytes):
            self.data = output
        else:
            self.data = output.encode('utf-8')
            ct = outheaders.get('Content-Type')
            if not ct:
                outheaders.set('Content-Type', 'text/plain; charset=UTF-8', replace_all=True)
        self.content_length = len(self.data)
        self.etag = None
        self.accept_ranges = False

    def write(self, dest):
        dest.write(self.data)
        self.data = None

    def write_compressed(self, dest):
        write_compressed_file_obj(BytesIO(self.data), dest)

class GeneratedOutput(object):

    def __init__(self, output, outheaders):
        self.output = output
        self.content_length = self.etag = None
        self.accept_ranges = False

    def write(self, dest):
        for line in self.output:
            if line:
                write_chunked_data(dest, line)

class StaticGeneratedOutput(object):

    def __init__(self, data):
        if isinstance(data, type('')):
            data = data.encode('utf-8')
        self.data = data
        self.etag = '"%s"' % hashlib.sha1(data).hexdigest()
        self.content_length = len(data)
        self.accept_ranges = False

    def write(self, dest):
        dest.write(self.data)

    def write_compressed(self, dest):
        write_compressed_file_obj(BytesIO(self.data), dest)

def generate_static_output(cache, gso_lock, name, generator):
    with gso_lock:
        ans = cache.get(name)
        if ans is None:
            ans = cache[name] = StaticGeneratedOutput(generator())
        return ans

def parse_if_none_match(val):
    return {x.strip() for x in val.split(',')}

def finalize_output(output, inheaders, outheaders, status_code, is_http1, method, opts):
    ct = outheaders.get('Content-Type', '')
    compressible = not ct or ct.startswith('text/') or ct.startswith('image/svg') or ct.startswith('application/json')
    stat_result = file_metadata(output)
    if stat_result is not None:
        output = FileSystemOutputFile(output, outheaders, stat_result, opts.use_sendfile)
        if 'Content-Type' not in outheaders:
            mt = guess_type(output.name)[0]
            if mt:
                if mt in ('text/plain', 'text/html'):
                    mt =+ '; charset=UTF-8'
                outheaders['Content-Type'] = mt
    elif isinstance(output, (bytes, type(''))):
        output = DynamicOutput(output, outheaders)
    elif hasattr(output, 'read'):
        output = ReadableOutput(output, outheaders)
    elif isinstance(output, StaticGeneratedOutput):
        pass
    else:
        output = GeneratedOutput(output, outheaders)
    compressible = (status_code == httplib.OK and compressible and
                    (opts.compress_min_size > -1 and output.content_length >= opts.compress_min_size) and
                    acceptable_encoding(inheaders.get('Accept-Encoding', '')) and not is_http1)
    accept_ranges = (not compressible and output.accept_ranges is not None and status_code == httplib.OK and
                     not is_http1)
    ranges = get_ranges(inheaders.get('Range'), output.content_length) if output.accept_ranges and method in ('GET', 'HEAD') else None
    if_range = (inheaders.get('If-Range') or '').strip()
    if if_range and if_range != output.etag:
        ranges = None
    if ranges is not None and not ranges:
        raise RangeNotSatisfiable(output.content_length)

    for header in ('Accept-Ranges', 'Content-Encoding', 'Transfer-Encoding', 'ETag', 'Content-Length'):
        outheaders.pop('header', all=True)

    none_match = parse_if_none_match(inheaders.get('If-None-Match', ''))
    matched = '*' in none_match or (output.etag and output.etag in none_match)
    if matched:
        raise IfNoneMatch(output.etag)

    if output.etag and method in ('GET', 'HEAD'):
        outheaders.set('ETag', output.etag, replace_all=True)
    if accept_ranges:
        outheaders.set('Accept-Ranges', 'bytes', replace_all=True)
    elif compressible:
        outheaders.set('Content-Encoding', 'gzip', replace_all=True)
    if output.content_length is not None and not compressible and not ranges:
        outheaders.set('Content-Length', '%d' % output.content_length, replace_all=True)

    if compressible or output.content_length is None:
        outheaders.set('Transfer-Encoding', 'chunked', replace_all=True)

    if ranges:
        if len(ranges) == 1:
            r = ranges[0]
            outheaders.set('Content-Length', '%d' % r.size, replace_all=True)
            outheaders.set('Content-Range', 'bytes %d-%d/%d' % (r.start, r.stop, output.content_length), replace_all=True)
            output.commit = partial(output.write_ranges, r)
        else:
            range_parts = get_range_parts(ranges, outheaders.get('Content-Type'), output.content_length)
            size = sum(map(len, range_parts)) + sum(r.size + 4 for r in ranges)
            outheaders.set('Content-Length', '%d' % size, replace_all=True)
            outheaders.set('Content-Type', 'multipart/byteranges; boundary=' + MULTIPART_SEPARATOR, replace_all=True)
            output.commit = partial(output.write_ranges, izip_longest(ranges, range_parts))
        status_code = httplib.PARTIAL_CONTENT
    else:
        output.commit = output.write_compressed if compressible else output.write

    return status_code, output
