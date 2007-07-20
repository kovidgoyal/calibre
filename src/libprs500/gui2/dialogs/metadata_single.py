##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
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
""" 
The dialog used to edit meta information for a book as well as 
add/remove formats
"""
import os

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QPixmap, QListWidgetItem, QErrorMessage, \
                    QVariant, QSettings, QFileDialog, QDialog


from libprs500.gui2.dialogs.metadata_single_ui import Ui_MetadataSingleDialog

class Format(QListWidgetItem):
    def __init__(self, parent, ext, path=None):
        self.path = path
        self.ext = ext
        QListWidgetItem.__init__(self, ext.upper(), parent, \
                        QListWidgetItem.UserType)

class EditBookDialog(Ui_MetadataSingleDialog, QDialog):
    
    def select_cover(self, checked):
        settings = QSettings()
        _dir = settings.value("change cover dir", \
                        QVariant(os.path.expanduser("~"))).toString()
        _file = str(QFileDialog.getOpenFileName(self.parent, \
            "Choose cover for " + str(self.title.text()), _dir, \
            "Images (*.png *.gif *.jpeg *.jpg);;All files (*)"))
        if len(_file):
            _file = os.path.abspath(_file)
            settings.setValue("change cover dir", \
                                        QVariant(os.path.dirname(_file)))
            if not os.access(_file, os.R_OK):
                QErrorMessage(self.parent).showMessage("You do not have "+\
                                        "permission to read the file: " + _file)
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e: 
                QErrorMessage(self.parent).showMessage("There was an error"+\
                                " reading from file: " + _file + "\n"+str(e))
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover, "", Qt.AutoColor)
                if pix.isNull(): 
                    QErrorMessage(self.parent).showMessage(_file + \
                                    " is not a valid picture")
                else:
                    self.cover_path.setText(_file)
                    self.cover.setPixmap(pix)                    
    
    
    def add_format(self, x):
        settings = QSettings()
        _dir = settings.value("add formats dialog dir", \
                            QVariant(os.path.expanduser("~"))).toString()
        files = QFileDialog.getOpenFileNames(self.parent, \
                "Choose formats for " + str(self.title.text()), _dir, \
                "Books (*.lrf *.lrx *.rtf *.txt *.html *.xhtml *.htm *.rar);;"+\
                "All files (*)")
        if not files.isEmpty():
            x = str(files[0])
            settings.setValue("add formats dialog dir", \
                                        QVariant(os.path.dirname(x)))
            files = str(files.join("|||")).split("|||")      
            for _file in files:
                _file = os.path.abspath(_file)
                if not os.access(_file, os.R_OK):
                    QErrorMessage(self.parent).showMessage("You do not have "+\
                                        "permission to read the file: " + _file)
                    continue
                ext = os.path.splitext(_file)[1].lower()
                if '.' in ext:
                    ext = ext.replace('.', '')
                for row in range(self.formats.count()):
                    fmt = self.formats.item(row)
                    if fmt.ext == ext:
                        self.formats.takeItem(row)
                        break
                Format(self.formats, ext, path=_file)
                self.formats_changed = True
    
    def remove_format(self, x):
        rows = self.formats.selectionModel().selectedRows(0)
        for row in rows:
            self.formats.takeItem(row.row())
            self.formats_changed = True
    
    def sync_formats(self):
        old_extensions, new_extensions, paths = set(), set(), {}
        for row in range(self.formats.count()):
            fmt = self.formats.item(row)
            ext, path = fmt.ext, fmt.path
            if "unknown" in ext.lower():
                ext = None
            if path:
                new_extensions.add(ext)
                paths[ext] = path
            else:
                old_extensions.add(ext)
        for ext in new_extensions:
            self.db.add_format(self.id, ext, file(paths[ext], "rb"))
        db_extensions = self.db.get_extensions(self.id)
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions:
                self.db.remove_format(self.id, ext)
        self.db.update_max_size(self.id)
    
    def __init__(self, parent, row, db):
        Ui_MetadataSingleDialog.__init__(self)
        QDialog.__init__(parent)
        self.setupUi(parent)
        self.splitter.setStretchFactor(100, 1)
        self.db = db
        self.id = db.id(row)
        self.cover_data = None
        self.formats_changed = False
        QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), \
                                                    self.select_cover)
        QObject.connect(self.add_format_button, SIGNAL("clicked(bool)"), \
                                                    self.add_format)
        QObject.connect(self.remove_format_button, SIGNAL("clicked(bool)"), \
                                                self.remove_format)
        QObject.connect(self.button_box, SIGNAL("accepted()"), \
                                                self.sync_formats)
        
        data = self.db.get_row_by_id(self.id, \
                    ["title","authors","rating","publisher","tags","comments"])
        self.title.setText(db.title(row))
        au = self.db.authors(row)
        self.authors.setText(au if au else '')
        pub = self.db.publisher(row)
        self.publisher.setText(pub if pub else '')
        tags = self.db.tags(row)
        self.tags.setText(tags if tags else '')
        rating = self.db.rating(row)
        if rating > 0: 
            self.rating.setValue(rating)
        self.comments.setPlainText(data["comments"] if data["comments"] else "")
        cover = self.db.cover(row)
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull(): 
                self.cover.setPixmap(pm)
#        exts = self.db.get_extensions(self.id)
#        for ext in exts:
#            if not ext:
#                ext = "Unknown"
#            Format(self.formats, ext)
