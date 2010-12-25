#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from calibre.gui2 import gprefs
from calibre.gui2.catalog.catalog_csv_xml_ui import Ui_Form
from calibre.library.database2 import LibraryDatabase2
from calibre.utils.config import prefs
from PyQt4.Qt import QWidget, QListWidgetItem

class PluginWidget(QWidget, Ui_Form):

    TITLE = _('CSV/XML Options')
    HELP  = _('Options specific to')+' CSV/XML '+_('output')
    sync_enabled = False
    formats = set(['csv', 'xml'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        from calibre.library.catalog import FIELDS
        self.all_fields = []
        for x in FIELDS:
            if x != 'all':
                self.all_fields.append(x)
                QListWidgetItem(x, self.db_fields)

        dbpath = os.path.abspath(prefs['library_path'])
        db = LibraryDatabase2(dbpath)
        for x in  sorted(db.custom_field_keys()):
            self.all_fields.append(x)
            QListWidgetItem(x, self.db_fields)


    def initialize(self, name, db):
        self.name = name
        fields = gprefs.get(name+'_db_fields', self.all_fields)
        # Restore the activated fields from last use
        for x in range(self.db_fields.count()):
            item = self.db_fields.item(x)
            item.setSelected(unicode(item.text()) in fields)

    def options(self):
        # Save the currently activated fields
        fields = []
        for x in range(self.db_fields.count()):
            item = self.db_fields.item(x)
            if item.isSelected():
                fields.append(unicode(item.text()))
        gprefs.set(self.name+'_db_fields', fields)

        # Return a dictionary with current options for this widget
        if len(self.db_fields.selectedItems()):
            return {'fields':[unicode(item.text()) for item in self.db_fields.selectedItems()]}
        else:
            return {'fields':['all']}
