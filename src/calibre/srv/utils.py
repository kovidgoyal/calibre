#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import errno, socket, select, os, time
from Cookie import SimpleCookie
from contextlib import closing
from urlparse import parse_qs
import repr as reprlib
from email.utils import formatdate
from operator import itemgetter
from future_builtins import map
from urllib import quote as urlquote
from binascii import hexlify, unhexlify

from calibre import prints
from calibre.constants import iswindows
from calibre.srv.errors import HTTPNotFound
from calibre.utils.config_base import tweaks
from calibre.utils.localization import get_translator
from calibre.utils.socket_inheritance import set_socket_inherit
from calibre.utils.logging import ThreadSafeLog
from calibre.utils.shared_file import share_open, raise_winerror

HTTP1  = 'HTTP/1.0'
HTTP11 = 'HTTP/1.1'
DESIRED_SEND_BUFFER_SIZE = 16 * 1024  # windows 7 uses an 8KB sndbuf


def http_date(timeval=None):
    return type('')(formatdate(timeval=timeval, usegmt=True))


class MultiDict(dict):  # {{{

    def __setitem__(self, key, val):
        vals = dict.get(self, key, [])
        vals.append(val)
        dict.__setitem__(self, key, vals)

    def __getitem__(self, key):
        return dict.__getitem__(self, key)[-1]

    @staticmethod
    def create_from_query_string(qs):
        ans = MultiDict()
        for k, v in parse_qs(qs, keep_blank_values=True).iteritems():
            dict.__setitem__(ans, k.decode('utf-8'), [x.decode('utf-8') for x in v])
        return ans

    def update_from_listdict(self, ld):
        for key, values in ld.iteritems():
            for val in values:
                self[key] = val

    def items(self, duplicates=True):
        for k, v in dict.iteritems(self):
            if duplicates:
                for x in v:
                    yield k, x
            else:
                yield k, v[-1]
    iteritems = items

    def values(self, duplicates=True):
        for v in dict.itervalues(self):
            if duplicates:
                for x in v:
                    yield x
            else:
                yield v[-1]
    itervalues = values

    def set(self, key, val, replace_all=False):
        if replace_all:
            dict.__setitem__(self, key, [val])
        else:
            self[key] = val

    def get(self, key, default=None, all=False):
        if all:
            try:
                return dict.__getitem__(self, key)
            except KeyError:
                return []
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def pop(self, key, default=None, all=False):
        ans = dict.pop(self, key, default)
        if ans is default:
            return [] if all else default
        return ans if all else ans[-1]

    def __repr__(self):
        return '{' + ', '.join('%s: %s' % (reprlib.repr(k), reprlib.repr(v)) for k, v in self.iteritems()) + '}'
    __str__ = __unicode__ = __repr__

    def pretty(self, leading_whitespace=''):
        return leading_whitespace + ('\n' + leading_whitespace).join(
            '%s: %s' % (k, (repr(v) if isinstance(v, bytes) else v)) for k, v in sorted(self.items(), key=itemgetter(0)))
# }}}


def error_codes(*errnames):
    ''' Return error numbers for error names, ignoring non-existent names '''
    ans = {getattr(errno, x, None) for x in errnames}
    ans.discard(None)
    return ans


socket_errors_eintr = error_codes("EINTR", "WSAEINTR")

socket_errors_socket_closed = error_codes(  # errors indicating a disconnected connection
    "EPIPE",
    "EBADF", "WSAEBADF",
    "ENOTSOCK", "WSAENOTSOCK",
    "ENOTCONN", "WSAENOTCONN",
    "ESHUTDOWN", "WSAESHUTDOWN",
    "ETIMEDOUT", "WSAETIMEDOUT",
    "ECONNREFUSED", "WSAECONNREFUSED",
    "ECONNRESET", "WSAECONNRESET",
    "ECONNABORTED", "WSAECONNABORTED",
    "ENETRESET", "WSAENETRESET",
    "EHOSTDOWN", "EHOSTUNREACH",
)
socket_errors_nonblocking = error_codes(
    'EAGAIN', 'EWOULDBLOCK', 'WSAEWOULDBLOCK')


def start_cork(sock):
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)


def stop_cork(sock):
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)


def create_sock_pair(port=0):
    '''Create socket pair. Works also on windows by using an ephemeral TCP port.'''
    if hasattr(socket, 'socketpair'):
        client_sock, srv_sock = socket.socketpair()
        set_socket_inherit(client_sock, False), set_socket_inherit(srv_sock, False)
        return client_sock, srv_sock

    # Create a non-blocking temporary server socket
    temp_srv_sock = socket.socket()
    set_socket_inherit(temp_srv_sock, False)
    temp_srv_sock.setblocking(False)
    temp_srv_sock.bind(('127.0.0.1', port))
    port = temp_srv_sock.getsockname()[1]
    temp_srv_sock.listen(1)
    with closing(temp_srv_sock):
        # Create non-blocking client socket
        client_sock = socket.socket()
        client_sock.setblocking(False)
        set_socket_inherit(client_sock, False)
        try:
            client_sock.connect(('127.0.0.1', port))
        except socket.error as err:
            # EWOULDBLOCK is not an error, as the socket is non-blocking
            if err.errno not in socket_errors_nonblocking:
                raise

        # Use select to wait for connect() to succeed.
        timeout = 1
        readable = select.select([temp_srv_sock], [], [], timeout)[0]
        if temp_srv_sock not in readable:
            raise Exception('Client socket not connected in {} second(s)'.format(timeout))
        srv_sock = temp_srv_sock.accept()[0]
        set_socket_inherit(srv_sock, False)
        client_sock.setblocking(True)

    return client_sock, srv_sock


def parse_http_list(header_val):
    """Parse lists as described by RFC 2068 Section 2.

    In particular, parse comma-separated lists where the elements of
    the list may include quoted-strings.  A quoted-string could
    contain a comma.  A non-quoted string could have quotes in the
    middle.  Neither commas nor quotes count if they are escaped.
    Only double-quotes count, not single-quotes.
    """
    if isinstance(header_val, bytes):
        slash, dquote, comma = b'\\",'
        empty = b''
    else:
        slash, dquote, comma = '\\",'
        empty = ''

    part = empty
    escape = quote = False
    for cur in header_val:
        if escape:
            part += cur
            escape = False
            continue
        if quote:
            if cur == slash:
                escape = True
                continue
            elif cur == dquote:
                quote = False
            part += cur
            continue

        if cur == comma:
            yield part.strip()
            part = empty
            continue

        if cur == dquote:
            quote = True

        part += cur

    if part:
        yield part.strip()


def parse_http_dict(header_val):
    'Parse an HTTP comma separated header with items of the form a=1, b="xxx" into a dictionary'
    if not header_val:
        return {}
    ans = {}
    sep, dquote = b'="' if isinstance(header_val, bytes) else '="'
    for item in parse_http_list(header_val):
        k, v = item.partition(sep)[::2]
        if k:
            if v.startswith(dquote) and v.endswith(dquote):
                v = v[1:-1]
            ans[k] = v
    return ans


def sort_q_values(header_val):
    'Get sorted items from an HTTP header of type: a;q=0.5, b;q=0.7...'
    if not header_val:
        return []

    def item(x):
        e, r = x.partition(';')[::2]
        p, v = r.partition('=')[::2]
        q = 1.0
        if p == 'q' and v:
            try:
                q = max(0.0, min(1.0, float(v.strip())))
            except Exception:
                pass
        return e.strip(), q
    return tuple(map(itemgetter(0), sorted(map(item, parse_http_list(header_val)), key=itemgetter(1), reverse=True)))


def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if getattr(e, 'errno', None) in socket_errors_eintr:
                continue
            raise


def get_translator_for_lang(cache, bcp_47_code):
    try:
        return cache[bcp_47_code]
    except KeyError:
        pass
    cache[bcp_47_code] = ans = get_translator(bcp_47_code)
    return ans


def encode_path(*components):
    'Encode the path specified as a list of path components using URL encoding'
    return '/' + '/'.join(urlquote(x.encode('utf-8'), '').decode('ascii') for x in components)


def encode_name(name):
    'Encode a name (arbitrary string) as URL safe characters. See decode_name() also.'
    if isinstance(name, unicode):
        name = name.encode('utf-8')
    return hexlify(name)


def decode_name(name):
    return unhexlify(name).decode('utf-8')


class Cookie(SimpleCookie):

    def _BaseCookie__set(self, key, real_value, coded_value):
        if not isinstance(key, bytes):
            key = key.encode('ascii')  # Python 2.x cannot handle unicode keys
        return SimpleCookie._BaseCookie__set(self, key, real_value, coded_value)


def custom_fields_to_display(db):
    ckeys = set(db.field_metadata.ignorable_field_keys())
    yes_fields = set(tweaks['content_server_will_display'])
    no_fields = set(tweaks['content_server_wont_display'])
    if '*' in yes_fields:
        yes_fields = ckeys
    if '*' in no_fields:
        no_fields = ckeys
    return frozenset(ckeys & (yes_fields - no_fields))

# Logging {{{


class ServerLog(ThreadSafeLog):
    exception_traceback_level = ThreadSafeLog.WARN


class RotatingStream(object):

    def __init__(self, filename, max_size=None, history=5):
        self.filename, self.history, self.max_size = filename, history, max_size
        if iswindows:
            self.filename = '\\\\?\\' + os.path.abspath(self.filename)
        self.set_output()

    def set_output(self):
        self.stream = share_open(self.filename, 'ab', -1 if iswindows else 1)  # line buffered
        try:
            self.current_pos = self.stream.tell()
        except EnvironmentError:
            # Happens if filename is /dev/stdout for example
            self.current_pos = 0
            self.max_size = None

    def flush(self):
        self.stream.flush()

    def prints(self, level, *args, **kwargs):
        kwargs['safe_encode'] = True
        kwargs['file'] = self.stream
        self.current_pos += prints(*args, **kwargs)
        if iswindows:
            # For some reason line buffering does not work on windows
            end = kwargs.get('end', b'\n')
            if b'\n' in end:
                self.flush()
        self.rollover()

    def rename(self, src, dest):
        try:
            if iswindows:
                import win32file, pywintypes
                try:
                    win32file.MoveFileEx(src, dest, win32file.MOVEFILE_REPLACE_EXISTING|win32file.MOVEFILE_WRITE_THROUGH)
                except pywintypes.error as e:
                    raise_winerror(e)
            else:
                os.rename(src, dest)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:  # the source of the rename does not exist
                raise

    def rollover(self):
        if not self.max_size or self.current_pos <= self.max_size or self.filename in ('/dev/stdout', '/dev/stderr'):
            return
        self.stream.close()
        for i in xrange(self.history - 1, 0, -1):
            src, dest = '%s.%d' % (self.filename, i), '%s.%d' % (self.filename, i+1)
            self.rename(src, dest)
        self.rename(self.filename, '%s.%d' % (self.filename, 1))
        self.set_output()

    def clear(self):
        if self.filename in ('/dev/stdout', '/dev/stderr'):
            return
        self.stream.close()
        failed = {}
        try:
            os.remove(self.filename)
        except EnvironmentError as e:
            failed[self.filename] = e
        import glob
        for f in glob.glob(self.filename + '.*'):
            try:
                os.remove(f)
            except EnvironmentError as e:
                failed[f] = e


class RotatingLog(ServerLog):

    def __init__(self, filename, max_size=None, history=5):
        ServerLog.__init__(self)
        self.outputs = [RotatingStream(filename, max_size, history)]

    def flush(self):
        for o in self.outputs:
            o.flush()
# }}}


class HandleInterrupt(object):  # {{{

    # On windows socket functions like accept(), recv(), send() are not
    # interrupted by a Ctrl-C in the console. So to make Ctrl-C work we have to
    # use this special context manager. See the echo server example at the
    # bottom of this file for how to use it.

    def __init__(self, action):
        if not iswindows:
            return  # Interrupts work fine on POSIX
        self.action = action
        from ctypes import WINFUNCTYPE, windll
        from ctypes.wintypes import BOOL, DWORD

        kernel32 = windll.LoadLibrary('kernel32')

        # <http://msdn.microsoft.com/en-us/library/ms686016.aspx>
        PHANDLER_ROUTINE = WINFUNCTYPE(BOOL, DWORD)
        self.SetConsoleCtrlHandler = kernel32.SetConsoleCtrlHandler
        self.SetConsoleCtrlHandler.argtypes = (PHANDLER_ROUTINE, BOOL)
        self.SetConsoleCtrlHandler.restype = BOOL

        @PHANDLER_ROUTINE
        def handle(event):
            if event == 0:  # CTRL_C_EVENT
                if self.action is not None:
                    self.action()
                    self.action = None
                # Typical C implementations would return 1 to indicate that
                # the event was processed and other control handlers in the
                # stack should not be executed.  However, that would
                # prevent the Python interpreter's handler from translating
                # CTRL-C to a `KeyboardInterrupt` exception, so we pretend
                # that we didn't handle it.
            return 0
        self.handle = handle

    def __enter__(self):
        if iswindows:
            if self.SetConsoleCtrlHandler(self.handle, 1) == 0:
                raise WindowsError()

    def __exit__(self, *args):
        if iswindows:
            if self.SetConsoleCtrlHandler(self.handle, 0) == 0:
                raise WindowsError()
# }}}


class Accumulator(object):  # {{{

    'Optimized replacement for BytesIO when the usage pattern is many writes followed by a single getvalue()'

    def __init__(self):
        self._buf = []
        self.total_length = 0

    def append(self, b):
        self._buf.append(b)
        self.total_length += len(b)

    def getvalue(self):
        ans = b''.join(self._buf)
        self._buf = []
        self.total_length = 0
        return ans
# }}}


def get_db(ctx, rd, library_id):
    db = ctx.get_library(rd, library_id)
    if db is None:
        raise HTTPNotFound('Library %r not found' % library_id)
    return db


def get_library_data(ctx, rd, strict_library_id=False):
    library_id = rd.query.get('library_id')
    library_map, default_library = ctx.library_info(rd)
    if library_id not in library_map:
        if strict_library_id and library_id:
            raise HTTPNotFound('No library with id: {}'.format(library_id))
        library_id = default_library
    db = get_db(ctx, rd, library_id)
    return db, library_id, library_map, default_library


class Offsets(object):
    'Calculate offsets for a paginated view'

    def __init__(self, offset, delta, total):
        if offset < 0:
            offset = 0
        if offset >= total:
            raise HTTPNotFound('Invalid offset: %r'%offset)
        last_allowed_index = total - 1
        last_current_index = offset + delta - 1
        self.slice_upper_bound = offset+delta
        self.offset = offset
        self.next_offset = last_current_index + 1
        if self.next_offset > last_allowed_index:
            self.next_offset = -1
        self.previous_offset = self.offset - delta
        if self.previous_offset < 0:
            self.previous_offset = 0
        self.last_offset = last_allowed_index - delta
        if self.last_offset < 0:
            self.last_offset = 0


_use_roman = None


def get_use_roman():
    global _use_roman
    if _use_roman is None:
        from calibre.gui2 import config
        _use_roman = config['use_roman_numerals_for_series_number']
    return _use_roman


if iswindows:
    def fast_now_strftime(fmt):
        fmt = fmt.encode('mbcs')
        return time.strftime(fmt).decode('mbcs', 'replace')
else:
    def fast_now_strftime(fmt):
        return time.strftime(fmt).decode('utf-8', 'replace')
