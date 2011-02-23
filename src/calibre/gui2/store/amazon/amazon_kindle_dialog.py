# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib

from PyQt4.Qt import QDialog, QUrl

from calibre.gui2.store.amazon.amazon_kindle_dialog_ui import Ui_Dialog

class AmazonKindleDialog(QDialog, Ui_Dialog):

    ASTORE_URL = 'http://astore.amazon.com/josbl0e-20/'

    def __init__(self, parent=None, start_item=None):
        QDialog.__init__(self, parent=parent)
        self.setupUi(self)
        
        self.view.loadStarted.connect(self.load_started)
        self.view.loadProgress.connect(self.load_progress)
        self.view.loadFinished.connect(self.load_finished)
        self.home.clicked.connect(self.go_home)
        self.reload.clicked.connect(self.go_reload)
        
        self.go_home(start_item=start_item)
        
    def load_started(self):
        self.progress.setValue(0)
    
    def load_progress(self, val):
        self.progress.setValue(val)
        
    def load_finished(self):
        self.progress.setValue(100)
    
    def go_home(self, checked=False, start_item=None):
        url = self.ASTORE_URL
        if start_item:
            url += 'detail/' + urllib.quote(start_item)
        self.view.load(QUrl(url))
        
    def go_reload(self, checked=False):
        self.view.reload()
