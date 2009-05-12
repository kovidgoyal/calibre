#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle
from multiprocessing.connection import Client
from threading import Thread
from queue import Queue
from contextlib import closing

PARALLEL_FUNCS = {
      'lrfviewer'    :
        ('calibre.gui2.lrf_renderer.main', 'main', None),

      'ebook-viewer'    :
        ('calibre.gui2.viewer.main', 'main', None),

      'render_pages' :
        ('calibre.ebooks.comic.input', 'render_pages', 'notification'),

      'gui_convert'     :
        ('calibre.gui2.convert.gui_conversion', 'gui_convert', 'notification'),
}

class Progress(Thread):

    def __init__(self, conn):
        self.daemon = True
        Thread.__init__(self)
        self.conn = conn
        self.queue = Queue()

    def __call__(self, percent, msg=''):
        self.queue.put((percent, msg))

    def run(self):
        while True:
            x = self.queue.get()
            if x is None:
                break
            try:
                self.conn.send(x)
            except:
                break



def get_func(name):
    module, func, notification = PARALLEL_FUNCS[name]
    module = __import__(module, fromlist=[1])
    func = getattr(module, func)
    return func, notification

def main():
    address = cPickle.loads(os.environ['CALIBRE_WORKER_ADDRESS'])
    key     = os.environ['CALIBRE_WORKER_KEY']
    with closing(Client(address, authkey=key)) as conn:
        name, args, kwargs = conn.recv()
        func, notification = get_func(name)
        notifier = Progress(conn)
        if notification:
            kwargs[notification] = notifier
            notifier.start()

        func(*args, **kwargs)

        notifier.queue.put(None)

    return 0



if __name__ == '__main__':
    raise SystemExit(main())
