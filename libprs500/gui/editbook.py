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
import sys, os, pkg_resources, StringIO
from PyQt4 import uic
from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.Qt import QObject, QDialog, QPixmap
from libprs500.lrf.meta import LRFMeta

ui = pkg_resources.resource_stream(__name__, "editbook.ui")
sys.path.append(os.path.dirname(ui.name))
Ui_BookEditDialog, bclass = uic.loadUiType(pkg_resources.resource_stream(__name__,  "editbook.ui"))

class EditBookDialog(Ui_BookEditDialog):
  
  def select_cover(self, checked):
    settings = QSettings()
    dir = settings.value("change cover dir", QVariant(os.path.expanduser("~"))).toString()
    file = QFileDialog.getOpenFileName(self.window, "Choose cover for " + str(self.title.text(), dir, "Images (*.png *.gif *.jpeg *.jpg);;All files (*)"))
    if len(str(file)):
      file = os.path.abspath(file)
      settings.setValue("change cover dir", QVariant(os.path.dirname(file)))
      if not os.access(file, os.R_OK):
        QErrorMessage(self.parent).showMessage("You do not have permission to read the file: " + file)
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
    tags = str(self.tags.text()).strip()
    publisher = str(self.publisher.text()).strip()
    comments = str(self.comments.toPlainText()).strip()
    self.db.set_metadata(self.id, title=title, authors=authors, tags=tags, publisher=publisher, comments=comments, cover=self.cover_data)
    lrf = self.db.get_format(self.id, "lrf")
    if lrf:
      lrf = StringIO.StringIO(lrf)
      lf = LRFMeta(lrf)
      if title: lf.title = title
      if authors: lf.title = authors
      if publisher: lf.publisher = publisher
      if self.cover_data: lf.thumbnail = self.cover_data
      self.db.add_format(self.id, "lrf", lrf.getvalue())
    
  
  def __init__(self, dialog, id, db):
    Ui_BookEditDialog.__init__(self)
    self.parent = dialog
    self.setupUi(dialog)
    self.db = db
    self.id = id
    self.cover_data = None
    QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), self.select_cover)
    QObject.connect(self.button_box, SIGNAL("accepted()"), self.write_data)
    data = self.db.get_row_by_id(self.id, ["title","authors","publisher","tags","comments"])
    self.title.setText(data["title"])
    self.authors.setText(data["authors"] if data["authors"] else "")
    self.publisher.setText(data["publisher"] if data["publisher"] else "")
    self.tags.setText(data["tags"] if data["tags"] else "")
    self.comments.setPlainText(data["comments"] if data["comments"] else "")
    cover = self.db.get_cover(self.id)
    if cover:
      pm = QPixmap()
      pm.loadFromData(cover, "", Qt.AutoColor)
      self.cover.setPixmap(pm)
    else: 
      self.cover.setPixmap(QPixmap(":/default_cover"))
