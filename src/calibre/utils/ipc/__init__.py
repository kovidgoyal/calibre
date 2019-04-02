#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, errno
from threading import Thread

from calibre import force_unicode
from calibre.constants import iswindows, get_windows_username, islinux, filesystem_encoding, ispy3
from calibre.utils.filenames import ascii_filename

VADDRESS = None


def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if getattr(e, 'errno', None) == errno.EINTR:
                continue
            raise


def gui_socket_address():
    if gui_socket_address.ans is None:
        if iswindows:
            gui_socket_address.ans = r'\\.\pipe\CalibreGUI'
            try:
                user = get_windows_username()
            except:
                user = None
            if user:
                user = ascii_filename(user).replace(' ', '_')
                if user:
                    gui_socket_address.ans += '-' + user[:100] + 'x'
        else:
            user = os.environ.get('USER', '')
            if not user:
                user = os.path.basename(os.path.expanduser('~'))
            if islinux:
                gui_socket_address.ans = (u'\0%s-calibre-gui.socket' % ascii_filename(force_unicode(user)))
            else:
                from tempfile import gettempdir
                tmp = gettempdir()
                gui_socket_address.ans = os.path.join(tmp, user+'-calibre-gui.socket')
        if not ispy3 and not isinstance(gui_socket_address.ans, bytes):
            gui_socket_address.ans = gui_socket_address.ans.encode(filesystem_encoding)
    return gui_socket_address.ans


def viewer_socket_address():
    if viewer_socket_address.ans is None:
        if iswindows:
            viewer_socket_address.ans = r'\\.\pipe\CalibreViewer'
            try:
                user = get_windows_username()
            except:
                user = None
            if user:
                user = ascii_filename(user).replace(' ', '_')
                if user:
                    viewer_socket_address.ans += '-' + user[:100] + 'x'
        else:
            user = os.environ.get('USER', '')
            if not user:
                user = os.path.basename(os.path.expanduser('~'))
            if islinux:
                viewer_socket_address.ans = (u'\0%s-calibre-viewer.socket' % ascii_filename(force_unicode(user)))
            else:
                from tempfile import gettempdir
                tmp = gettempdir()
                viewer_socket_address.ans = os.path.join(tmp, user+'-calibre-viewer.socket')
        if not ispy3 and not isinstance(viewer_socket_address.ans, bytes):
            viewer_socket_address.ans = viewer_socket_address.ans.encode(filesystem_encoding)
    return viewer_socket_address.ans


gui_socket_address.ans = viewer_socket_address.ans = None


class RC(Thread):

    def __init__(self, print_error=True, socket_address=None):
        self.print_error = print_error
        self.socket_address = socket_address or gui_socket_address()
        Thread.__init__(self)
        self.conn = None
        self.daemon = True

    def run(self):
        from multiprocessing.connection import Client
        self.done = False
        try:
            self.conn = Client(self.socket_address)
            self.done = True
        except:
            if self.print_error:
                import traceback
                traceback.print_exc()
