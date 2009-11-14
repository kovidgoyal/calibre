#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QDialog, QDialogButtonBox, Qt, QLabel, QVBoxLayout, \
        SIGNAL, QThread

from calibre.ebooks.metadata import MetaInformation

class Worker(QThread):

    def __init__(self, mi, parent):
        QThread.__init__(self, parent)
        self.mi = MetaInformation(mi)
        self.exceptions = []

    def run(self):
        from calibre.ebooks.metadata.fetch import get_social_metadata
        self.exceptions = get_social_metadata(self.mi)

class SocialMetadata(QDialog):

    def __init__(self, mi, parent):
        QDialog.__init__(self, parent)

        self.bbox = QDialogButtonBox(QDialogButtonBox.Ok, Qt.Horizontal, self)
        self.mi = mi
        self.layout = QVBoxLayout(self)
        self.label = QLabel(_('Downloading social metadata, please wait...'), self)
        self.label.setWordWrap(True)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.bbox)

        self.worker = Worker(mi, self)
        self.connect(self.worker, SIGNAL('finished()'), self.accept)
        self.connect(self.bbox, SIGNAL('rejected()'), self.reject)
        self.worker.start()

    def reject(self):
        self.disconnect(self.worker, SIGNAL('finished()'), self.accept)
        QDialog.reject(self)

    def accept(self):
        self.mi.tags = self.worker.mi.tags
        self.mi.rating = self.worker.mi.rating
        self.mi.comments = self.worker.mi.comments
        QDialog.accept(self)

    @property
    def exceptions(self):
        return self.worker.exceptions
