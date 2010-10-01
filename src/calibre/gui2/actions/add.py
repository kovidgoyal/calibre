#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QInputDialog, QPixmap, QMenu


from calibre.gui2 import error_dialog, choose_files, \
    choose_dir, warning_dialog, info_dialog
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.filenames import ascii_filename
from calibre.constants import preferred_encoding, filesystem_encoding
from calibre.gui2.actions import InterfaceAction

class AddAction(InterfaceAction):

    name = 'Add Books'
    action_spec = (_('Add books'), 'add_book.png',
            _('Add books to the calibre library/device from files on your computer')
            , _('A'))
    action_type = 'current'

    def genesis(self):
        self._add_filesystem_book = self.Dispatcher(self.__add_filesystem_book)
        self.add_menu = QMenu()
        self.add_menu.addAction(_('Add books from a single directory'),
                self.add_books)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub-directories (One book per directory, assumes every ebook '
            'file is the same book in a different format)'),
            self.add_recursive_single)
        self.add_menu.addAction(_('Add books from directories, including '
            'sub directories (Multiple books per directory, assumes every '
            'ebook file is a different book)'), self.add_recursive_multiple)
        self.add_menu.addSeparator()
        self.add_menu.addAction(_('Add Empty book. (Book entry with no '
            'formats)'), self.add_empty)
        self.add_menu.addAction(_('Add from ISBN'), self.add_from_isbn)
        self.qaction.setMenu(self.add_menu)
        self.qaction.triggered.connect(self.add_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.add_menu.actions())[1:]:
            action.setEnabled(enabled)

    def add_recursive(self, single):
        root = choose_dir(self.gui, 'recursive book import root dir dialog',
                          'Select root folder')
        if not root:
            return
        from calibre.gui2.add import Adder
        self._adder = Adder(self.gui,
                self.gui.library_view.model().db,
                self.Dispatcher(self._files_added), spare_server=self.gui.spare_server)
        self._adder.add_recursive(root, single)

    def add_recursive_single(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming one book per folder.
        '''
        self.add_recursive(True)

    def add_recursive_multiple(self, *args):
        '''
        Add books from the local filesystem to either the library or the device
        recursively assuming multiple books per folder.
        '''
        self.add_recursive(False)

    def add_empty(self, *args):
        '''
        Add an empty book item to the library. This does not import any formats
        from a book file.
        '''
        num, ok = QInputDialog.getInt(self.gui, _('How many empty books?'),
                _('How many empty books should be added?'), 1, 1, 100)
        if ok:
            from calibre.ebooks.metadata import MetaInformation
            for x in xrange(num):
                self.gui.library_view.model().db.import_book(MetaInformation(None), [])
            self.gui.library_view.model().books_added(num)

    def add_isbns(self, isbns):
        from calibre.ebooks.metadata import MetaInformation
        ids = set([])
        for x in isbns:
            mi = MetaInformation(None)
            mi.isbn = x
            ids.add(self.gui.library_view.model().db.import_book(mi, []))
        self.gui.library_view.model().books_added(len(isbns))
        self.gui.iactions['Edit Metadata'].do_download_metadata(ids)


    def files_dropped(self, paths):
        to_device = self.gui.stack.currentIndex() != 0
        self._add_books(paths, to_device)

    def files_dropped_on_book(self, event, paths):
        accept = False
        if self.gui.current_view() is not self.gui.library_view:
            return
        db = self.gui.library_view.model().db
        current_idx = self.gui.library_view.currentIndex()
        if not current_idx.isValid(): return
        cid = db.id(current_idx.row())
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext:
                ext = ext[1:]
            if ext in IMAGE_EXTENSIONS:
                pmap = QPixmap()
                pmap.load(path)
                if not pmap.isNull():
                    accept = True
                    db.set_cover(cid, pmap)
            elif ext in BOOK_EXTENSIONS:
                db.add_format_with_hooks(cid, ext, path, index_is_id=True)
                accept = True
        if accept:
            event.accept()
            self.gui.library_view.model().current_changed(current_idx, current_idx)

    def __add_filesystem_book(self, paths, allow_device=True):
        if isinstance(paths, basestring):
            paths = [paths]
        books = [path for path in map(os.path.abspath, paths) if os.access(path,
            os.R_OK)]

        if books:
            to_device = allow_device and self.gui.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.gui.status_bar.show_message(\
                        _('Uploading books to device.'), 2000)


    def add_filesystem_book(self, paths, allow_device=True):
        self._add_filesystem_book(paths, allow_device=allow_device)

    def add_from_isbn(self, *args):
        from calibre.gui2.dialogs.add_from_isbn import AddFromISBN
        d = AddFromISBN(self.gui)
        if d.exec_() == d.Accepted:
            self.add_isbns(d.isbns)

    def add_books(self, *args):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        filters = [
                        (_('Books'), BOOK_EXTENSIONS),
                        (_('EPUB Books'), ['epub']),
                        (_('LRF Books'), ['lrf']),
                        (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
                        (_('LIT Books'), ['lit']),
                        (_('MOBI Books'), ['mobi', 'prc', 'azw']),
                        (_('Topaz books'), ['tpz','azw1']),
                        (_('Text books'), ['txt', 'rtf']),
                        (_('PDF Books'), ['pdf']),
                        (_('Comics'), ['cbz', 'cbr', 'cbc']),
                        (_('Archives'), ['zip', 'rar']),
                        ]
        to_device = self.gui.stack.currentIndex() != 0
        if to_device:
            filters = [(_('Supported books'), self.gui.device_manager.device.FORMATS)]

        books = choose_files(self.gui, 'add books dialog dir', 'Select books',
                             filters=filters)
        if not books:
            return
        self._add_books(books, to_device)

    def _add_books(self, paths, to_device, on_card=None):
        if on_card is None:
            on_card = 'carda' if self.gui.stack.currentIndex() == 2 else \
                      'cardb' if self.gui.stack.currentIndex() == 3 else None
        if not paths:
            return
        from calibre.gui2.add import Adder
        self.__adder_func = partial(self._files_added, on_card=on_card)
        self._adder = Adder(self.gui,
                None if to_device else self.gui.library_view.model().db,
                self.Dispatcher(self.__adder_func), spare_server=self.gui.spare_server)
        self._adder.add(paths)

    def _files_added(self, paths=[], names=[], infos=[], on_card=None):
        if paths:
            self.gui.upload_books(paths,
                                list(map(ascii_filename, names)),
                                infos, on_card=on_card)
            self.gui.status_bar.show_message(
                    _('Uploading books to device.'), 2000)
        if getattr(self._adder, 'number_of_books_added', 0) > 0:
            self.gui.library_view.model().books_added(self._adder.number_of_books_added)
            if hasattr(self.gui, 'db_images'):
                self.gui.db_images.reset()
        if getattr(self._adder, 'merged_books', False):
            books = u'\n'.join([x if isinstance(x, unicode) else
                    x.decode(preferred_encoding, 'replace') for x in
                    self._adder.merged_books])
            info_dialog(self.gui, _('Merged some books'),
                    _('Some duplicates were found and merged into the '
                        'following existing books:'), det_msg=books, show=True)
        if getattr(self._adder, 'critical', None):
            det_msg = []
            for name, log in self._adder.critical.items():
                if isinstance(name, str):
                    name = name.decode(filesystem_encoding, 'replace')
                det_msg.append(name+'\n'+log)

            warning_dialog(self.gui, _('Failed to read metadata'),
                    _('Failed to read metadata from the following')+':',
                    det_msg='\n\n'.join(det_msg), show=True)

        if hasattr(self._adder, 'cleanup'):
            self._adder.cleanup()
        self._adder = None

    def _add_from_device_adder(self, paths=[], names=[], infos=[],
                               on_card=None, model=None):
        self._files_added(paths, names, infos, on_card=on_card)
        # set the in-library flags, and as a consequence send the library's
        # metadata for this book to the device. This sets the uuid to the
        # correct value. Note that set_books_in_library might sync_booklists
        self.gui.set_books_in_library(booklists=[model.db], reset=True)
        self.gui.refresh_ondevice()

    def add_books_from_device(self, view):
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Add to library'), _('No book selected'))
            d.exec_()
            return
        paths = [p for p in view._model.paths(rows) if p is not None]
        ve = self.gui.device_manager.device.VIRTUAL_BOOK_EXTENSIONS
        def ext(x):
            ans = os.path.splitext(x)[1]
            ans = ans[1:] if len(ans) > 1 else ans
            return ans.lower()
        remove = set([p for p in paths if ext(p) in ve])
        if remove:
            paths = [p for p in paths if p not in remove]
            info_dialog(self.gui,  _('Not Implemented'),
                        _('The following books are virtual and cannot be added'
                          ' to the calibre library:'), '\n'.join(remove),
                        show=True)
            if not paths:
                return
        if not paths or len(paths) == 0:
            d = error_dialog(self.gui, _('Add to library'), _('No book files found'))
            d.exec_()
            return
        from calibre.gui2.add import Adder
        self.__adder_func = partial(self._add_from_device_adder, on_card=None,
                                                    model=view._model)
        self._adder = Adder(self.gui, self.gui.library_view.model().db,
                self.Dispatcher(self.__adder_func), spare_server=self.gui.spare_server)
        self._adder.add(paths)


