#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from threading import Thread
from multiprocessing.connection import arbitrary_address, Listener

from calibre.constants import iswindows

class Server(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True

        self.auth_key = os.urandom(32)
        self.address = arbitrary_address('AF_PIPE' if iswindows else 'AF_UNIX')
        if iswindows and self.address[1] == ':':
            self.address = self.address[2:]
        self.listener = Listener(address=self.address,
                authkey=self.auth_key, backlog=4)

        self.keep_going = True

    def stop(self):
        self.keep_going = False
        try:
            self.listener.close()
        except:
            pass

    def run(self):
        while self.keep_going:
            try:
                conn = self.listener.accept()
                self.handle_client(conn)
            except:
                pass


