__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''' 
The dialog used to edit meta information for a book as well as 
add/remove formats
'''
import os

from PyQt4.QtCore import SIGNAL, QObject, QCoreApplication, Qt, QVariant
from PyQt4.QtGui import QPixmap, QListWidgetItem, QErrorMessage, QDialog


from calibre.gui2 import qstring_to_unicode, error_dialog, file_icon_provider, \
                           choose_files, pixmap_to_data, choose_images
from calibre.gui2.dialogs.metadata_single_ui import Ui_MetadataSingleDialog
from calibre.gui2.dialogs.fetch_metadata import FetchMetadata
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.gui2.dialogs.password import PasswordDialog
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.library_thing import login, cover_from_isbn, LibraryThingError
from calibre import Settings

class Format(QListWidgetItem):
    def __init__(self, parent, ext, size, path=None):
        self.path = path
        self.ext = ext
        self.size = float(size)/(1024*1024)
        text = '%s (%.2f MB)'%(self.ext.upper(), self.size)
        QListWidgetItem.__init__(self, file_icon_provider().icon_from_ext(ext), 
                                 text, parent, QListWidgetItem.UserType)

class MetadataSingleDialog(QDialog, Ui_MetadataSingleDialog):
    
    def select_cover(self, checked):
        files = choose_images(self, 'change cover dialog', 
                             u'Choose cover for ' + qstring_to_unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self.window, _('Cannot read'), 
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e: 
                d = error_dialog(self.window, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self.window, _file + " is not a valid picture")
                    d.exec_()
                else:
                    self.cover_path.setText(_file)
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix                  
    
    
    def add_format(self, x):
        files = choose_files(self, 'add formats dialog', 
                             "Choose formats for " + str(self.title.text()),
                             [('Books', BOOK_EXTENSIONS)])
        if not files: 
            return      
        for _file in files:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                QErrorMessage(self.window).showMessage("You do not have "+\
                                    "permission to read the file: " + _file)
                continue
            size = os.stat(_file).st_size
            ext = os.path.splitext(_file)[1].lower()
            if '.' in ext:
                ext = ext.replace('.', '')
            for row in range(self.formats.count()):
                fmt = self.formats.item(row)
                if fmt.ext == ext:
                    self.formats.takeItem(row)
                    break
            Format(self.formats, ext, size, path=_file)
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
            if 'unknown' in ext.lower():
                ext = None
            if path:
                new_extensions.add(ext)
                paths[ext] = path
            else:
                old_extensions.add(ext)
        for ext in new_extensions:
            self.db.add_format(self.row, ext, open(paths[ext], "rb"))
        db_extensions = set(self.db.formats(self.row).split(','))
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions:
                self.db.remove_format(self.row, ext)
    
    def __init__(self, window, row, db):
        QDialog.__init__(self, window)
        Ui_MetadataSingleDialog.__init__(self)        
        self.setupUi(self)
        self.splitter.setStretchFactor(100, 1)
        self.db = db
        self.id = db.id(row)
        self.row = row
        self.cover_data = None
        self.formats_changed = False
        self.cover_changed = False
        self.cpixmap = None
        self.changed = False
        QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), \
                                                    self.select_cover)
        QObject.connect(self.add_format_button, SIGNAL("clicked(bool)"), \
                                                    self.add_format)
        QObject.connect(self.remove_format_button, SIGNAL("clicked(bool)"), \
                                                self.remove_format)
        QObject.connect(self.fetch_metadata_button, SIGNAL('clicked()'), 
                        self.fetch_metadata)
        
        QObject.connect(self.fetch_cover_button, SIGNAL('clicked()'), 
                        self.fetch_cover)
        QObject.connect(self.tag_editor_button, SIGNAL('clicked()'), 
                        self.edit_tags)
        QObject.connect(self.remove_series_button, SIGNAL('clicked()'),
                        self.remove_unused_series)        
        self.timeout = float(Settings().value('network timeout', QVariant(5)).toInt()[0])
        self.title.setText(db.title(row))
        isbn = db.isbn(self.id, index_is_id=True)
        if not isbn:
            isbn = ''
        self.isbn.setText(isbn)
        au = self.db.authors(row)
        self.authors.setText(au if au else '')
        aus = self.db.author_sort(row)
        self.author_sort.setText(aus if aus else '')
        pub = self.db.publisher(row)
        self.publisher.setText(pub if pub else '')
        tags = self.db.tags(row)
        self.tags.setText(tags if tags else '')
        rating = self.db.rating(row)
        if rating > 0: 
            self.rating.setValue(int(rating/2.))
        comments = self.db.comments(row)
        self.comments.setPlainText(comments if comments else '')
        cover = self.db.cover(row)
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull(): 
                self.cover.setPixmap(pm)
        exts = self.db.formats(row)
        if exts:
            exts = exts.split(',')        
            for ext in exts:
                if not ext:
                    ext = ''
                size = self.db.sizeof_format(row, ext)
                Format(self.formats, ext, size)
            
        self.initialize_series()
            
        self.series_index.setValue(self.db.series_index(row))
        QObject.connect(self.series, SIGNAL('currentIndexChanged(int)'), self.enable_series_index)
        QObject.connect(self.series, SIGNAL('editTextChanged(QString)'), self.enable_series_index)
        QObject.connect(self.password_button, SIGNAL('clicked()'), self.change_password) 

        self.exec_()

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))
        series_id = self.db.series_id(self.row)
        idx, c = None, 0
        for i in all_series:
            id, name = i
            if id == series_id:
                idx = c
            self.series.addItem(name)
            c += 1
        
        self.series.lineEdit().setText('')
        if idx is not None:
            self.series.setCurrentIndex(idx)
            self.enable_series_index()
        
        pl = self.series.parentWidget().layout()
        for i in range(pl.count()):
            l =  pl.itemAt(i).layout()
            if l:
                l.invalidate()
                l.activate()
                
        self.layout().activate()
    
    def edit_tags(self):
        d = TagEditor(self, self.db, self.row)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
    
    def lt_password_dialog(self):
        return PasswordDialog(self, 'LibraryThing account', 
                 _('<p>Enter your username and password for <b>LibraryThing.com</b>. <br/>If you do not have one, you can <a href=\'http://www.librarything.com\'>register</a> for free!.</p>'))
    
    def change_password(self):
        d = self.lt_password_dialog() 
        d.exec_()
    
    def fetch_cover(self):
        isbn   = qstring_to_unicode(self.isbn.text())
        if isbn:
            d = self.lt_password_dialog() 
            if not d.username() or not d.password():
                d.exec_()
                if d.result() != PasswordDialog.Accepted:
                    return
            self.fetch_cover_button.setEnabled(False)
            self.setCursor(Qt.WaitCursor)
            QCoreApplication.instance().processEvents()
            try:
                login(d.username(), d.password(), force=False)
                cover_data = cover_from_isbn(isbn, timeout=self.timeout)[0]
            
                pix = QPixmap()
                pix.loadFromData(cover_data)
                if pix.isNull():
                    error_dialog(self.window, "The cover is not a valid picture").exec_()
                else:
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix   
            except LibraryThingError, err:
                error_dialog(self, _('Could not fetch cover'), _('<b>Could not fetch cover.</b><br/>')+str(err)).exec_()
            finally:
                self.fetch_cover_button.setEnabled(True)
                self.unsetCursor()
                
        else:
            error_dialog(self, _('Cannot fetch cover'), _('You must specify the ISBN identifier for this book.')).exec_()
                
    
    def fetch_metadata(self):
        isbn   = qstring_to_unicode(self.isbn.text())
        title  = qstring_to_unicode(self.title.text())
        author = qstring_to_unicode(self.authors.text()).split(',')[0]
        publisher = qstring_to_unicode(self.publisher.text()) 
        if isbn or title or author or publisher:
            d = FetchMetadata(self, isbn, title, author, publisher, self.timeout)
            d.exec_()
            if d.result() == QDialog.Accepted:
                book = d.selected_book()
                if book:
                    self.title.setText(book.title)
                    self.authors.setText(', '.join(book.authors))
                    if book.author_sort: self.author_sort.setText(book.author_sort)
                    self.publisher.setText(book.publisher)
                    self.isbn.setText(book.isbn)
                    summ = book.comments
                    if summ:
                        prefix = qstring_to_unicode(self.comments.toPlainText())
                        if prefix:
                            prefix += '\n'
                        self.comments.setText(prefix + summ)
        else:
            error_dialog(self, 'Cannot fetch metadata', 'You must specify at least one of ISBN, Title, Authors or Publisher')
             
    def enable_series_index(self, *args):
        self.series_index.setEnabled(True)
    
    def remove_unused_series(self):
        self.db.remove_unused_series()
        idx = qstring_to_unicode(self.series.currentText())
        self.series.clear()
        self.initialize_series()
        if idx:
            for i in range(self.series.count()):
                if qstring_to_unicode(self.series.itemText(i)) == idx:
                    self.series.setCurrentIndex(i)
                    break
        
    
    def accept(self):
        if self.formats_changed:
            self.sync_formats()
        title = qstring_to_unicode(self.title.text())
        self.db.set_title(self.id, title)
        au = qstring_to_unicode(self.authors.text()).split(',')
        if au: self.db.set_authors(self.id, au)
        aus = qstring_to_unicode(self.author_sort.text())
        if aus:
            self.db.set_author_sort(self.id, aus)
        self.db.set_isbn(self.id, qstring_to_unicode(self.isbn.text()))
        self.db.set_rating(self.id, 2*self.rating.value())
        self.db.set_publisher(self.id, qstring_to_unicode(self.publisher.text()))
        self.db.set_tags(self.id, qstring_to_unicode(self.tags.text()).split(','))
        self.db.set_series(self.id, qstring_to_unicode(self.series.currentText()))
        self.db.set_series_index(self.id, self.series_index.value())
        self.db.set_comment(self.id, qstring_to_unicode(self.comments.toPlainText()))
        if self.cover_changed:
            self.db.set_cover(self.id, pixmap_to_data(self.cover.pixmap()))
        self.changed = True
        QDialog.accept(self)
    
