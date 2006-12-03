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
import sys, os, StringIO
from PyQt4 import uic
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QDialog, QPixmap, QListWidgetItem
from libprs500.lrf.meta import LRFMetaFile
from libprs500.gui import import_ui

class Format(QListWidgetItem):
  def __init__(self, parent, ext, data):
    self.data = data
    self.ext = ext
    QListWidgetItem.__init__(self, ext.upper(), parent, QListWidgetItem.UserType)

Ui_BookEditDialog = import_ui("editbook.ui")
class EditBookDialog(Ui_BookEditDialog):
  
  def select_cover(self, checked):
    settings = QSettings()
    dir = settings.value("change cover dir", QVariant(os.path.expanduser("~"))).toString()
    file = QFileDialog.getOpenFileName(self.window, "Choose cover for " + str(self.title.text()), dir, "Images (*.png *.gif *.jpeg *.jpg);;All files (*)")
    if len(str(file)):
      file = os.path.abspath(file)
      settings.setValue("change cover dir", QVariant(os.path.dirname(file)))
      if not os.access(file, os.R_OK):
        QErrorMessage(self.parent).showMessage("You do not have permission to read the file: " + file)
        return
      cf, cover = None, None
      try:
        cf = open(file, "rb")
        cover = cf.read()
      except IOError, e: QErrorMessage(self.parent).showMessage("There was an error reading from file: " + file + "\n"+str(e))
      if cover:
        pix = QPixmap()
        pix.loadFromData(cover, "", Qt.AutoColor)
        if pix.isNull(): QErrorMessage(self.parent).showMessage(file + " is not a valid picture")
        else:
          self.cover_path.setText(file)
          self.cover.setPixmap(pix)
          self.cover_data = cover
        
  
  def write_data(self):
    title = str(self.title.text()).strip()
    authors = str(self.authors.text()).strip()
    rating = self.rating.value()
    tags = str(self.tags.text()).strip()
    publisher = str(self.publisher.text()).strip()
    comments = str(self.comments.toPlainText()).strip()
    self.db.set_metadata(self.id, title=title, authors=authors, rating=rating, tags=tags, publisher=publisher, comments=comments, cover=self.cover_data)
    if self.formats_changed:
      for r in range(self.formats.count()):
        format = self.formats.item(r)
        self.db.add_format(self.id, format.ext, format.data)    
    lrf = self.db.get_format(self.id, "lrf")
    if lrf:
      lrf = StringIO.StringIO(lrf)
      lf = LRFMetaFile(lrf)
      if title: lf.title = title
      if authors: lf.title = authors
      if publisher: lf.publisher = publisher
      if self.cover_data: lf.thumbnail = self.cover_data
      self.db.add_format(self.id, "lrf", lrf.getvalue())
    
  
  def add_format(self, x):
    dir = settings.value("add formats dialog dir", QVariant(os.path.expanduser("~"))).toString()
    files = QFileDialog.getOpenFileNames(self.window, "Choose formats for " + str(self.title.text()), dir, "Books (*.lrf *.lrx *.rtf *.txt *.html *.xhtml *.htm *.rar);;All files (*)")
    if not files.isEmpty():
      x = str(files[0])
      settings.setValue("add formats dialog dir", QVariant(os.path.dirname(x)))
      files = str(files.join("|||")).split("|||")      
      for file in files:
        file = os.path.abspath(file)
        if not os.access(file, os.R_OK):
          QErrorMessage(self.parent).showMessage("You do not have permission to read the file: " + file)
          continue
        f, data = None, None
        try:
          f = open(file, "rb")
          data = f.read()
        except IOError, e: QErrorMessage(self.parent).showMessage("There was an error reading from file: " + file + "\n"+str(e))
        if data:
          ext = file[file.rfind(".")+1:].lower() if file.find(".") > -1 else None
          Format(self.formats, ext, data)
          self.formats_changed = True
    
  def remove_format(self, x):
    rows = self.formats.selectionModel().selectedRows(0)
    for row in rows:
      item = self.formats.takeItem(row.row())
      self.formats_changed = True
  
  def __init__(self, dialog, id, db):
    Ui_BookEditDialog.__init__(self)
    self.parent = dialog
    self.setupUi(dialog)
    self.splitter.setStretchFactor(100,1)
    self.db = db
    self.id = id
    self.cover_data = None
    self.formats_changed = False
    QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), self.select_cover)
    QObject.connect(self.button_box, SIGNAL("accepted()"), self.write_data)
    QObject.connect(self.add_format_button, SIGNAL("clicked(bool)"), self.add_format)
    QObject.connect(self.remove_format_button, SIGNAL("clicked(bool)"), self.remove_format)
    data = self.db.get_row_by_id(self.id, ["title","authors","rating","publisher","tags","comments"])
    self.title.setText(data["title"])
    self.authors.setText(data["authors"] if data["authors"] else "")
    self.publisher.setText(data["publisher"] if data["publisher"] else "")
    self.tags.setText(data["tags"] if data["tags"] else "")
    if data["rating"] > 0: self.rating.setValue(data["rating"])
    self.comments.setPlainText(data["comments"] if data["comments"] else "")
    cover = self.db.get_cover(self.id)
    if cover:
      pm = QPixmap()
      pm.loadFromData(cover, "", Qt.AutoColor)
      self.cover.setPixmap(pm)
    else: 
      self.cover.setPixmap(QPixmap(":/default_cover"))
