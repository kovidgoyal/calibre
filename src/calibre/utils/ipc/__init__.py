#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from threading import Thread

from calibre.constants import iswindows

ADDRESS = r'\\.\pipe\CalibreGUI' if iswindows else \
    os.path.expanduser('~/.calibre-gui.socket')

class RC(Thread):

    def __init__(self, print_error=True):
        self.print_error = print_error
        Thread.__init__(self)
        self.conn = None

    def run(self):
        from multiprocessing.connection import Client
        self.done = False
        try:
            self.conn = Client(ADDRESS)
            self.done = True
        except:
            if self.print_error:
                import traceback
                traceback.print_exc()


