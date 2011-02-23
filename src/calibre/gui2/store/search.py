# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from threading import Event, Thread
from Queue import Queue

from PyQt4.Qt import QDialog, QTimer

from calibre.customize.ui import store_plugins
from calibre.gui2.store.search_ui import Ui_Dialog

class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

        self.store_plugins = {}
        self.running_threads = []
        self.results = Queue()
        self.abort = Event()
        self.checker = QTimer()

        for x in store_plugins():
            self.store_plugins[x.name] = x
            
        self.search.clicked.connect(self.do_search)
        self.checker.timeout.connect(self.get_results)
        
    def do_search(self, checked=False):
        # Stop all running threads.
        self.checker.stop()
        self.abort.set()
        self.running_threads = []
        self.results = Queue()
        self.abort = Event()
        for n in self.store_plugins:
            t = SearchThread(unicode(self.search_edit.text()), (n, self.store_plugins[n]), self.results, self.abort)
            self.running_threads.append(t)
            t.start()
        if self.running_threads:
            self.checker.start(100)
            
    def get_results(self):
        running = False
        for t in self.running_threads:
            if t.is_alive():
                running = True
        if not running:
            self.checker.stop()
        
        while not self.results.empty():
            print self.results.get_nowait()


class SearchThread(Thread):
    
    def __init__(self, query, store, results, abort):
        Thread.__init__(self)
        self.daemon = True
        self.query = query
        self.store_name = store[0]
        self.store_plugin = store[1]
        self.results = results
        self.abort = abort
    
    def run(self):
        if self.abort.is_set():
            return
        for res in self.store_plugin.search(self.query):
            self.results.put((self.store_name, res))
