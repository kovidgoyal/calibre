#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
import os

from calibre import force_unicode
from calibre.constants import (
    filesystem_encoding, get_windows_username, islinux, iswindows
)
from calibre.utils.filenames import ascii_filename
from polyglot.functools import lru_cache

VADDRESS = None


def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except OSError as e:
            if getattr(e, 'errno', None) == errno.EINTR:
                continue
            raise


@lru_cache()
def socket_address(which):
    if iswindows:
        ans = r'\\.\pipe\Calibre' + which
        try:
            user = get_windows_username()
        except Exception:
            user = None
        if user:
            user = ascii_filename(user).replace(' ', '_')
            if user:
                ans += '-' + user[:100] + 'x'
    else:
        user = force_unicode(os.environ.get('USER') or os.path.basename(os.path.expanduser('~')), filesystem_encoding)
        sock_name = '{}-calibre-{}.socket'.format(ascii_filename(user).replace(' ', '_'), which)
        if islinux:
            ans = '\0' + sock_name
        else:
            from tempfile import gettempdir
            tmp = force_unicode(gettempdir(), filesystem_encoding)
            ans = os.path.join(tmp, sock_name)
    return ans


def gui_socket_address():
    return socket_address('GUI' if iswindows else 'gui')


def viewer_socket_address():
    return socket_address('Viewer' if iswindows else 'viewer')
