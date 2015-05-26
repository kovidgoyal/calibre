#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import errno, socket, select
from contextlib import closing
from urlparse import parse_qs
import repr as reprlib
from email.utils import formatdate
from operator import itemgetter

from calibre.constants import iswindows

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
        for k, v in parse_qs(qs, keep_blank_values=True):
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
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)

def stop_cork(sock):
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if hasattr(socket, 'TCP_CORK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)

def create_sock_pair(port=0):
    '''Create socket pair. Works also on windows by using an ephemeral TCP port.'''
    if hasattr(socket, 'socketpair'):
        client_sock, srv_sock = socket.socketpair()
        return client_sock, srv_sock

    # Create a non-blocking temporary server socket
    temp_srv_sock = socket.socket()
    temp_srv_sock.setblocking(False)
    temp_srv_sock.bind(('localhost', port))
    port = temp_srv_sock.getsockname()[1]
    temp_srv_sock.listen(1)
    with closing(temp_srv_sock):
        # Create non-blocking client socket
        client_sock = socket.socket()
        client_sock.setblocking(False)
        while True:
            try:
                client_sock.connect(('localhost', port))
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
        client_sock.setblocking(True)

    return client_sock, srv_sock

def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if getattr(e, 'errno', None) in socket_errors_eintr:
                continue
            raise

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

class Accumulator(object):

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
