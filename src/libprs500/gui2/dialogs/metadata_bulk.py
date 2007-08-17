##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

'''Dialog to edit metadata in bulk'''

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.QtGui import QDialog

from libprs500.gui2 import qstring_to_unicode
from libprs500.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog

class MetadataBulkDialog(QDialog, Ui_MetadataBulkDialog):
    def __init__(self, window, rows, db):
        QDialog.__init__(self, window)
        Ui_MetadataBulkDialog.__init__(self)
        self.setupUi(self.dialog)
        self.db = db
        self.ids = [ db.id(r) for r in rows]
        self.write_series = False
        self.write_rating = False
        self.changed = False
        QObject.connect(self.button_box, SIGNAL("accepted()"), self.sync)        
        QObject.connect(self.series, SIGNAL('currentIndexChanged(int)'), self.series_changed)
        QObject.connect(self.series, SIGNAL('editTextChanged(QString)'), self.series_changed)
        QObject.connect(self.rating, SIGNAL('valueChanged(int)'), self.rating_changed)
        
        all_series = self.db.all_series()
        
        for i in all_series:
            id, name = i
            self.series.addItem(name)
            
        self.series.lineEdit().setText('')
        
        self.dialog.exec_()
            
        
    def sync(self):
        for id in self.ids:
            au = qstring_to_unicode(self.authors.text())
            if au:
                au = au.split(',')
                self.db.set_authors(id, au)
            if self.write_rating:
                self.db.set_rating(id, 2*self.rating.value())
            pub = qstring_to_unicode(self.publisher.text())
            if pub:
                self.db.set_publisher(id, pub)
            tags = qstring_to_unicode(self.tags.text())
            if tags:
                tags = tags.split(tags)
                self.db.set_tags(id, tags, append=True)
            if self.write_series:
                self.db.set_series(id, qstring_to_unicode(self.series.currentText()))
        self.changed = True
    
    def series_changed(self):
        self.write_series = True
        
    def rating_changed(self):
        self.write_rating = True