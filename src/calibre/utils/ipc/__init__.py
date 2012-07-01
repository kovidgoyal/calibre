#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, errno
from threading import Thread

from calibre.constants import iswindows, get_windows_username

ADDRESS = None

def eintr_retry_call(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except EnvironmentError as e:
            if getattr(e, 'errno', None) == errno.EINTR:
                continue
            raise

def gui_socket_address():
    global ADDRESS
    if ADDRESS is None:
        if iswindows:
            ADDRESS = r'\\.\pipe\CalibreGUI'
            try:
                user = get_windows_username()
            except:
                user = None
            if user:
                from calibre.utils.filenames import ascii_filename
                user = ascii_filename(user).replace(' ', '_')
                if user:
                    ADDRESS += '-' + user[:100] + 'x'
        else:
            from tempfile import gettempdir
            tmp = gettempdir()
            user = os.environ.get('USER', '')
            if not user:
                user = os.path.basename(os.path.expanduser('~'))
            ADDRESS = os.path.join(tmp, user+'-calibre-gui.socket')
    return ADDRESS

class RC(Thread):

    def __init__(self, print_error=True):
        self.print_error = print_error
        Thread.__init__(self)
        self.conn = None

    def run(self):
        from multiprocessing.connection import Client
        self.done = False
        try:
            self.conn = Client(gui_socket_address())
            self.done = True
        except:
            if self.print_error:
                import traceback
                traceback.print_exc()


