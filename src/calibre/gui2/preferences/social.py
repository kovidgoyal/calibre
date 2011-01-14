#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from threading import Thread

from PyQt4.Qt import QDialog, QDialogButtonBox, Qt, QLabel, QVBoxLayout, \
        QTimer

from calibre.ebooks.metadata import MetaInformation

class Worker(Thread):

    def __init__(self, mi):
        Thread.__init__(self)
        self.daemon = True
        self.mi = MetaInformation(mi)
        self.exceptions = []

    def run(self):
        from calibre.ebooks.metadata.fetch import get_social_metadata
        self.exceptions = get_social_metadata(self.mi)

class SocialMetadata(QDialog):

    TIMEOUT = 300 # seconds

    def __init__(self, mi, parent):
        QDialog.__init__(self, parent)

        self.bbox = QDialogButtonBox(QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.mi = mi
        self.layout = QVBoxLayout(self)
        self.label = QLabel(_('Downloading social metadata, please wait...'), self)
        self.label.setWordWrap(True)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.bbox)

        self.worker = Worker(mi)
        self.bbox.rejected.connect(self.reject)
        self.worker.start()
        self.start_time = time.time()
        self.timed_out = False
        self.rejected = False
        QTimer.singleShot(50, self.update)

    def reject(self):
        self.rejected = True
        QDialog.reject(self)

    def update(self):
        if self.rejected:
            return
        if time.time() - self.start_time > self.TIMEOUT:
            self.timed_out = True
            self.reject()
            return
        if not self.worker.is_alive():
            self.accept()
        QTimer.singleShot(50, self.update)

    def accept(self):
        self.mi.tags = self.worker.mi.tags
        self.mi.rating = self.worker.mi.rating
        self.mi.comments = self.worker.mi.comments
        if self.worker.mi.series:
            self.mi.series = self.worker.mi.series
            self.mi.series_index = self.worker.mi.series_index
        QDialog.accept(self)

    @property
    def exceptions(self):
        return self.worker.exceptions
