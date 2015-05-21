#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import errno, socket
from urlparse import parse_qs
import repr as reprlib
from email.utils import formatdate

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
        return leading_whitespace + ('\n' + leading_whitespace).join('%s: %s' % (k, v) for k, v in self.items())
# }}}

def error_codes(*errnames):
    ''' Return error numbers for error names, ignoring non-existent names '''
    ans = {getattr(errno, x, None) for x in errnames}
    ans.discard(None)
    return ans

socket_error_eintr = error_codes("EINTR", "WSAEINTR")

socket_errors_to_ignore = error_codes(  # errors indicating a closed connection
    "EPIPE",
    "EBADF", "WSAEBADF",
    "ENOTSOCK", "WSAENOTSOCK",
    "ETIMEDOUT", "WSAETIMEDOUT",
    "ECONNREFUSED", "WSAECONNREFUSED",
    "ECONNRESET", "WSAECONNRESET",
    "ECONNABORTED", "WSAECONNABORTED",
    "ENETRESET", "WSAENETRESET",
    "EHOSTDOWN", "EHOSTUNREACH",
)
socket_errors_nonblocking = error_codes(
    'EAGAIN', 'EWOULDBLOCK', 'WSAEWOULDBLOCK')

class Corked(object):

    ' Context manager to turn on TCP corking. Ensures maximum throughput for large logical packets. '

    def __init__(self, sock):
        self.sock = sock if hasattr(socket, 'TCP_CORK') else None

    def __enter__(self):
        if self.sock is not None:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)

    def __exit__(self, *args):
        if self.sock is not None:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)
            self.sock.send(b'')  # Ensure that uncorking occurs
