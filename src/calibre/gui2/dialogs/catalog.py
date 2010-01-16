#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QDialog

from calibre.gui2.dialogs.catalog_ui import Ui_Dialog
from calibre.gui2 import dynamic
from calibre.customize.ui import available_catalog_formats

class Catalog(QDialog, Ui_Dialog):

    def __init__(self, parent, dbspec, ids):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.dbspec, self.ids = dbspec, ids

        self.count.setText(unicode(self.count.text()).format(len(ids)))
        self.title.setText(dynamic.get('catalog_last_used_title',
            _('My Books')))
        fmts = sorted([x.upper() for x in available_catalog_formats()])

        self.format.currentIndexChanged.connect(self.format_changed)

        self.format.addItems(fmts)

        pref = dynamic.get('catalog_preferred_format', 'EPUB')
        idx = self.format.findText(pref)
        if idx > -1:
            self.format.setCurrentIndex(idx)

        if self.sync.isEnabled():
            self.sync.setChecked(dynamic.get('catalog_sync_to_device', True))

    def format_changed(self, idx):
        cf = unicode(self.format.currentText())
        if cf in ('EPUB', 'MOBI'):
            self.sync.setEnabled(True)
        else:
            self.sync.setDisabled(True)
            self.sync.setChecked(False)

    def accept(self):
        self.catalog_format = unicode(self.format.currentText())
        dynamic.set('catalog_preferred_format', self.catalog_format)
        self.catalog_title = unicode(self.title.text())
        dynamic.set('catalog_last_used_title', self.catalog_title)
        self.catalog_sync = bool(self.sync.isChecked())
        dynamic.set('catalog_sync_to_device', self.catalog_sync)
        QDialog.accept(self)
