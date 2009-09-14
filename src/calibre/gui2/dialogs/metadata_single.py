__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
The dialog used to edit meta information for a book as well as
add/remove formats
'''

import os
import re
import time
import traceback
from datetime import datetime

from PyQt4.QtCore import SIGNAL, QObject, QCoreApplication, Qt, QTimer, QThread, QDate
from PyQt4.QtGui import QPixmap, QListWidgetItem, QErrorMessage, QDialog

from calibre.gui2 import qstring_to_unicode, error_dialog, file_icon_provider, \
                           choose_files, choose_images, ResizableDialog
from calibre.gui2.dialogs.metadata_single_ui import Ui_MetadataSingleDialog
from calibre.gui2.dialogs.fetch_metadata import FetchMetadata
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.gui2.widgets import ProgressIndicator
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import authors_to_sort_string, string_to_authors, authors_to_string
from calibre.ebooks.metadata.library_thing import cover_from_isbn
from calibre import islinux
from calibre.ebooks.metadata.meta import get_metadata
from calibre.utils.config import prefs
from calibre.customize.ui import run_plugins_on_import

class CoverFetcher(QThread):

    def __init__(self, username, password, isbn, timeout, title, author):
        self.username = username.strip() if username else username
        self.password = password.strip() if password else password
        self.timeout = timeout
        self.isbn = isbn
        self.title = title
        self.needs_isbn = False
        self.author = author
        QThread.__init__(self)
        self.exception = self.traceback = self.cover_data = None

    def run(self):
        try:
            if not self.isbn:
                from calibre.ebooks.metadata.fetch import search
                if not self.title:
                    self.needs_isbn = True
                    return
                au = self.author if self.author else None
                key = prefs['isbndb_com_key']
                if not key:
                    key = None
                results = search(title=self.title, author=au,
                        isbndb_key=key)[0]
                results = sorted([x.isbn for x in results if x.isbn],
                        cmp=lambda x,y:cmp(len(x),len(y)), reverse=True)
                if not results:
                    self.needs_isbn = True
                    return
                self.isbn = results[0]

            self.cover_data = cover_from_isbn(self.isbn, timeout=self.timeout,
                    username=self.username, password=self.password)[0]
        except Exception, e:
            self.exception = e
            self.traceback = traceback.format_exc()
            print self.traceback



class Format(QListWidgetItem):
    def __init__(self, parent, ext, size, path=None):
        self.path = path
        self.ext = ext
        self.size = float(size)/(1024*1024)
        text = '%s (%.2f MB)'%(self.ext.upper(), self.size)
        QListWidgetItem.__init__(self, file_icon_provider().icon_from_ext(ext),
                                 text, parent, QListWidgetItem.UserType)

class MetadataSingleDialog(ResizableDialog, Ui_MetadataSingleDialog):

    COVER_FETCH_TIMEOUT = 240 # seconds

    def do_reset_cover(self, *args):
        pix = QPixmap(I('book.svg'))
        self.cover.setPixmap(pix)
        self.cover_changed = True
        self.cover_data = None

    def select_cover(self, checked):
        files = choose_images(self, 'change cover dialog',
                             _('Choose cover for ') + unicode(self.title.text()))
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
                    d = error_dialog(self.window,
                        _("Not a valid picture"),
                            _file + _(" is not a valid picture"))
                    d.exec_()
                else:
                    self.cover_path.setText(_file)
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix
                    self.cover_data = cover


    def add_format(self, x):
        files = choose_files(self, 'add formats dialog',
                             "Choose formats for " + qstring_to_unicode((self.title.text())),
                             [('Books', BOOK_EXTENSIONS)])
        if not files:
            return
        for _file in files:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                QErrorMessage(self.window).showMessage("You do not have "+\
                                    "permission to read the file: " + _file)
                continue
            _file = run_plugins_on_import(_file)
            size = os.stat(_file).st_size
            ext = os.path.splitext(_file)[1].lower().replace('.', '')
            for row in range(self.formats.count()):
                fmt = self.formats.item(row)
                if fmt.ext.lower() == ext:
                    self.formats.takeItem(row)
                    break
            Format(self.formats, ext, size, path=_file)
            self.formats_changed = True

    def remove_format(self, x):
        rows = self.formats.selectionModel().selectedRows(0)
        for row in rows:
            self.formats.takeItem(row.row())
            self.formats_changed = True

    def get_selected_format_metadata(self):
        row = self.formats.currentRow()
        fmt = self.formats.item(row)
        if fmt is None:
            if self.formats.count() == 1:
                fmt = self.formats.item(0)
            if fmt is None:
                error_dialog(self, _('No format selected'),
                    _('No format selected')).exec_()
                return None, None
        ext = fmt.ext.lower()
        if fmt.path is None:
            stream = self.db.format(self.row, ext, as_file=True)
        else:
            stream = open(fmt.path, 'r+b')
        try:
            mi = get_metadata(stream, ext)
            return mi, ext
        except:
            error_dialog(self, _('Could not read metadata'),
                         _('Could not read metadata from %s format')%ext).exec_()
        return None, None

    def set_metadata_from_format(self):
        mi, ext = self.get_selected_format_metadata()
        if mi is None:
            return
        if mi.title:
            self.title.setText(mi.title)
        if mi.authors:
            self.authors.setEditText(authors_to_string(mi.authors))
        if mi.author_sort:
            self.author_sort.setText(mi.author_sort)
        if mi.rating is not None:
            try:
                self.rating.setValue(mi.rating)
            except:
                pass
        if mi.publisher:
            self.publisher.setEditText(mi.publisher)
        if mi.tags:
            self.tags.setText(', '.join(mi.tags))
        if mi.isbn:
            self.isbn.setText(mi.isbn)
        if mi.pubdate:
            self.pubdate.setDate(QDate(mi.pubdate.year, mi.pubdate.month,
                mi.pubdate.day))
        if mi.series and mi.series.strip():
            self.series.setEditText(mi.series)
            if mi.series_index is not None:
                self.series_index.setValue(float(mi.series_index))

    def set_cover(self):
        mi, ext = self.get_selected_format_metadata()
        if mi is None:
            return
        cdata = None
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover).read()
        elif mi.cover_data[1] is not None:
            cdata = mi.cover_data[1]
        if cdata is None:
            error_dialog(self, _('Could not read cover'),
                         _('Could not read cover from %s format')%ext).exec_()
            return
        pix = QPixmap()
        pix.loadFromData(cdata)
        if pix.isNull():
            error_dialog(self, _('Could not read cover'),
                         _('The cover in the %s format is invalid')%ext).exec_()
            return
        self.cover.setPixmap(pix)
        self.cover_changed = True
        self.cpixmap = pix
        self.cover_data = cdata

    def sync_formats(self):
        old_extensions, new_extensions, paths = set(), set(), {}
        for row in range(self.formats.count()):
            fmt = self.formats.item(row)
            ext, path = fmt.ext.lower(), fmt.path
            if 'unknown' in ext.lower():
                ext = None
            if path:
                new_extensions.add(ext)
                paths[ext] = path
            else:
                old_extensions.add(ext)
        for ext in new_extensions:
            self.db.add_format(self.row, ext, open(paths[ext], 'rb'), notify=False)
        db_extensions = set([f.lower() for f in self.db.formats(self.row).split(',')])
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions:
                self.db.remove_format(self.row, ext, notify=False)

    def do_cancel_all(self):
        self.cancel_all = True
        self.reject()

    def __init__(self, window, row, db, accepted_callback=None, cancel_all=False):
        ResizableDialog.__init__(self, window)
        self.bc_box.layout().setAlignment(self.cover, Qt.AlignCenter|Qt.AlignHCenter)
        self.cancel_all = False
        if cancel_all:
            self.__abort_button = self.button_box.addButton(self.button_box.Abort)
            self.__abort_button.setToolTip(_('Abort the editing of all remaining books'))
            self.connect(self.__abort_button, SIGNAL('clicked()'),
                    self.do_cancel_all)
        self.splitter.setStretchFactor(100, 1)
        self.db = db
        self.pi = ProgressIndicator(self)
        self.accepted_callback = accepted_callback
        self.id = db.id(row)
        self.row = row
        self.cover_data = None
        self.formats_changed = False
        self.cover_changed = False
        self.cpixmap = None
        self.cover.setAcceptDrops(True)
        self.pubdate.setMinimumDate(QDate(100,1,1))
        self.connect(self.cover, SIGNAL('cover_changed(PyQt_PyObject)'), self.cover_dropped)
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
        QObject.connect(self.auto_author_sort, SIGNAL('clicked()'),
                        self.deduce_author_sort)
        self.connect(self.formats, SIGNAL('itemDoubleClicked(QListWidgetItem*)'),
                self.show_format)
        self.connect(self.button_set_cover, SIGNAL('clicked()'), self.set_cover)
        self.connect(self.button_set_metadata, SIGNAL('clicked()'),
                self.set_metadata_from_format)
        self.connect(self.reset_cover, SIGNAL('clicked()'), self.do_reset_cover)
        self.connect(self.swap_button, SIGNAL('clicked()'), self.swap_title_author)
        self.timeout = float(prefs['network_timeout'])
        self.title.setText(db.title(row))
        isbn = db.isbn(self.id, index_is_id=True)
        if not isbn:
            isbn = ''
        self.isbn.setText(isbn)
        aus = self.db.author_sort(row)
        self.author_sort.setText(aus if aus else '')
        tags = self.db.tags(row)
        self.tags.setText(', '.join(tags.split(',')) if tags else '')
        self.tags.update_tags_cache(self.db.all_tags())
        rating = self.db.rating(row)
        if rating > 0:
            self.rating.setValue(int(rating/2.))
        comments = self.db.comments(row)
        self.comments.setPlainText(comments if comments else '')
        cover = self.db.cover(row)
        pubdate = db.pubdate(self.id, index_is_id=True)
        self.pubdate.setDate(QDate(pubdate.year, pubdate.month,
            pubdate.day))

        exts = self.db.formats(row)
        if exts:
            exts = exts.split(',')
            for ext in exts:
                if not ext:
                    ext = ''
                size = self.db.sizeof_format(row, ext)
                if size is None:
                    continue
                Format(self.formats, ext, size)


        self.initialize_combos()
        si = self.db.series_index(row)
        if si is None:
            si = 1.0
        try:
            self.series_index.setValue(float(si))
        except:
            self.series_index.setValue(1.0)
        QObject.connect(self.series, SIGNAL('currentIndexChanged(int)'), self.enable_series_index)
        QObject.connect(self.series, SIGNAL('editTextChanged(QString)'), self.enable_series_index)

        self.show()
        height_of_rest = self.frameGeometry().height() - self.cover.height()
        width_of_rest  = self.frameGeometry().width() - self.cover.width()
        ag = QCoreApplication.instance().desktop().availableGeometry(self)
        self.cover.MAX_HEIGHT = ag.height()-(25 if islinux else 0)-height_of_rest
        self.cover.MAX_WIDTH = ag.width()-(25 if islinux else 0)-width_of_rest
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull():
                self.cover.setPixmap(pm)
            self.cover_data = cover

    def show_format(self, item, *args):
        fmt = item.ext
        self.emit(SIGNAL('view_format(PyQt_PyObject)'), fmt)

    def deduce_author_sort(self):
        au = unicode(self.authors.text())
        au = re.sub(r'\s+et al\.$', '', au)
        authors = string_to_authors(au)
        self.author_sort.setText(authors_to_sort_string(authors))

    def swap_title_author(self):
        title = self.title.text()
        self.title.setText(self.authors.text())
        self.authors.setText(title)
        self.author_sort.setText('')

    def cover_dropped(self, paths):
        self.cover_changed = True
        self.cover_data = self.cover.cover_data

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

        self.layout().activate()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(cmp=lambda x, y : cmp(x[1], y[1]))
        for i in all_authors:
            id, name = i
            name = [name.strip().replace('|', ',') for n in name.split(',')]
            self.authors.addItem(authors_to_string(name))

        au = self.db.authors(self.row)
        if not au:
            au = _('Unknown')
        au = ' & '.join([a.strip().replace('|', ',') for a in au.split(',')])
        self.authors.setEditText(au)

    def initialize_series(self):
        self.series.setSizeAdjustPolicy(self.series.AdjustToContentsOnFirstShow)
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

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(cmp=lambda x, y : cmp(x[1], y[1]))
        publisher_id = self.db.publisher_id(self.row)
        idx, c = None, 0
        for i in all_publishers:
            id, name = i
            if id == publisher_id:
                idx = c
            self.publisher.addItem(name)
            c += 1

        self.publisher.setEditText('')
        if idx is not None:
            self.publisher.setCurrentIndex(idx)

    def edit_tags(self):
        d = TagEditor(self, self.db, self.row)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())

    def fetch_cover(self):
        isbn   = re.sub(r'[^0-9a-zA-Z]', '', unicode(self.isbn.text())).strip()
        self.fetch_cover_button.setEnabled(False)
        self.setCursor(Qt.WaitCursor)
        title, author = map(unicode, (self.title.text(), self.authors.text()))
        self.cover_fetcher = CoverFetcher(None, None, isbn,
                                            self.timeout, title, author)
        self.cover_fetcher.start()
        self._hangcheck = QTimer(self)
        self.connect(self._hangcheck, SIGNAL('timeout()'), self.hangcheck)
        self.cf_start_time = time.time()
        self.pi.start(_('Downloading cover...'))
        self._hangcheck.start(100)

    def hangcheck(self):
        if not self.cover_fetcher.isFinished() and \
            time.time()-self.cf_start_time < self.COVER_FETCH_TIMEOUT:
            return

        self._hangcheck.stop()
        try:
            if self.cover_fetcher.isRunning():
                self.cover_fetcher.terminate()
                error_dialog(self, _('Cannot fetch cover'),
                    _('<b>Could not fetch cover.</b><br/>')+
                    _('The download timed out.')).exec_()
                return
            if self.cover_fetcher.needs_isbn:
                error_dialog(self, _('Cannot fetch cover'),
                    _('Could not find cover for this book. Try '
                      'specifying the ISBN first.')).exec_()
                return
            if self.cover_fetcher.exception is not None:
                err = self.cover_fetcher.exception
                error_dialog(self, _('Cannot fetch cover'),
                    _('<b>Could not fetch cover.</b><br/>')+repr(err)).exec_()
                return

            pix = QPixmap()
            pix.loadFromData(self.cover_fetcher.cover_data)
            if pix.isNull():
                error_dialog(self, _('Bad cover'),
                             _('The cover is not a valid picture')).exec_()
            else:
                self.cover.setPixmap(pix)
                self.cover_changed = True
                self.cpixmap = pix
                self.cover_data = self.cover_fetcher.cover_data
        finally:
            self.fetch_cover_button.setEnabled(True)
            self.unsetCursor()
            self.pi.stop()


    def fetch_metadata(self):
        isbn   = re.sub(r'[^0-9a-zA-Z]', '', unicode(self.isbn.text()))
        title  = qstring_to_unicode(self.title.text())
        author = string_to_authors(unicode(self.authors.text()))[0]
        publisher = qstring_to_unicode(self.publisher.currentText())
        if isbn or title or author or publisher:
            d = FetchMetadata(self, isbn, title, author, publisher, self.timeout)
            self._fetch_metadata_scope = d
            with d:
                if d.exec_() == QDialog.Accepted:
                    book = d.selected_book()
                    if book:
                        self.title.setText(book.title)
                        self.authors.setText(authors_to_string(book.authors))
                        if book.author_sort: self.author_sort.setText(book.author_sort)
                        if book.publisher: self.publisher.setEditText(book.publisher)
                        if book.isbn: self.isbn.setText(book.isbn)
                        if book.pubdate:
                            d = book.pubdate
                            self.pubdate.setDate(QDate(d.year, d.month, d.day))
                        summ = book.comments
                        if summ:
                            prefix = qstring_to_unicode(self.comments.toPlainText())
                            if prefix:
                                prefix += '\n'
                            self.comments.setText(prefix + summ)
        else:
            error_dialog(self, _('Cannot fetch metadata'),
                         _('You must specify at least one of ISBN, Title, '
                           'Authors or Publisher'))

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
        try:
            if self.formats_changed:
                self.sync_formats()
            title = unicode(self.title.text())
        except IOError, err:
            if err.errno == 13: # Permission denied
                fname = err.filename if err.filename else 'file'
                return error_dialog(self, _('Permission denied'),
                        _('Could not open %s. Is it being used by another'
                        ' program?')%fname, show=True)
            raise
        self.db.set_title(self.id, title, notify=False)
        au = unicode(self.authors.text())
        if au:
            self.db.set_authors(self.id, string_to_authors(au), notify=False)
        aus = qstring_to_unicode(self.author_sort.text())
        if aus:
            self.db.set_author_sort(self.id, aus, notify=False)
        self.db.set_isbn(self.id,
                 re.sub(r'[^0-9a-zA-Z]', '', unicode(self.isbn.text())), notify=False)
        self.db.set_rating(self.id, 2*self.rating.value(), notify=False)
        self.db.set_publisher(self.id, qstring_to_unicode(self.publisher.currentText()), notify=False)
        self.db.set_tags(self.id, qstring_to_unicode(self.tags.text()).split(','), notify=False)
        self.db.set_series(self.id, qstring_to_unicode(self.series.currentText()), notify=False)
        self.db.set_series_index(self.id, self.series_index.value(), notify=False)
        self.db.set_comment(self.id, qstring_to_unicode(self.comments.toPlainText()), notify=False)
        d = self.pubdate.date()
        self.db.set_pubdate(self.id, datetime(d.year(), d.month(), d.day()))

        if self.cover_changed and self.cover_data is not None:
            self.db.set_cover(self.id, self.cover_data)
        QDialog.accept(self)
        if callable(self.accepted_callback):
            self.accepted_callback(self.id)

    def reject(self, *args):
        cf = getattr(self, 'cover_fetcher', None)
        if cf is not None and hasattr(cf, 'terminate'):
            cf.terminate()
            cf.wait()

        QDialog.reject(self, *args)
