#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QPixmap, QTimer


from calibre.gui2 import error_dialog, choose_files, \
    choose_dir, warning_dialog, info_dialog
from calibre.gui2.dialogs.add_empty_book import AddEmptyBookDialog
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.widgets import IMAGE_EXTENSIONS
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.filenames import ascii_filename
from calibre.constants import preferred_encoding, filesystem_encoding
from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import question_dialog
from calibre.ebooks.metadata import MetaInformation

def get_filters():
    return [
            (_('Books'), BOOK_EXTENSIONS),
            (_('EPUB Books'), ['epub']),
            (_('LRF Books'), ['lrf']),
            (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
            (_('LIT Books'), ['lit']),
            (_('MOBI Books'), ['mobi', 'prc', 'azw']),
            (_('Topaz books'), ['tpz','azw1']),
            (_('Text books'), ['txt', 'text', 'rtf']),
            (_('PDF Books'), ['pdf', 'azw4']),
            (_('SNB Books'), ['snb']),
            (_('Comics'), ['cbz', 'cbr', 'cbc']),
            (_('Archives'), ['zip', 'rar']),
            (_('Wordprocessor files'), ['odt', 'doc', 'docx']),
    ]


class AddAction(InterfaceAction):

    name = 'Add Books'
    action_spec = (_('Add books'), 'add_book.png',
            _('Add books to the calibre library/device from files on your computer')
            , _('A'))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Add books from a single directory')

    def genesis(self):
        self._add_filesystem_book = self.Dispatcher(self.__add_filesystem_book)
        self.add_menu = self.qaction.menu()
        ma = partial(self.create_menu_action, self.add_menu)
        ma('recursive-single', _('Add books from directories, including '
            'sub-directories (One book per directory, assumes every ebook '
            'file is the same book in a different format)')).triggered.connect(
            self.add_recursive_single)
        ma('recursive-multiple', _('Add books from directories, including '
            'sub directories (Multiple books per directory, assumes every '
            'ebook file is a different book)')).triggered.connect(
                    self.add_recursive_multiple)
        self.add_menu.addSeparator()
        ma('add-empty', _('Add Empty book. (Book entry with no formats)'),
                shortcut=_('Shift+Ctrl+E')).triggered.connect(self.add_empty)
        ma('add-isbn', _('Add from ISBN')).triggered.connect(self.add_from_isbn)
        self.add_menu.addSeparator()
        ma('add-formats', _('Add files to selected book records'),
                triggered=self.add_formats, shortcut=_('Shift+A'))
        self.add_menu.addSeparator()
        ma('add-config', _('Control the adding of books'),
                triggered=self.add_config)

        self.qaction.triggered.connect(self.add_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.add_menu.actions())[1:]:
            action.setEnabled(enabled)

    def add_config(self):
        self.gui.iactions['Preferences'].do_config(
            initial_plugin=('Import/Export', 'Adding'),
            close_after_initial=True)

    def add_formats(self, *args):
        if self.gui.stack.currentIndex() != 0:
            return
        view = self.gui.library_view
        rows = view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, _('No books selected'),
                    _('Cannot add files as no books are selected'), show=True)
        ids = [view.model().id(r) for r in rows]

        if len(ids) > 1 and not question_dialog(self.gui,
                _('Are you sure'),
            _('Are you sure you want to add the same'
                ' files to all %d books? If the format'
                ' already exists for a book, it will be replaced.')%len(ids)):
                return

        books = choose_files(self.gui, 'add formats dialog dir',
                _('Select book files'), filters=get_filters())
        if not books:
            return

        db = view.model().db
        for id_ in ids:
            for fpath in books:
                fmt = os.path.splitext(fpath)[1][1:].upper()
                if fmt:
                    db.add_format_with_hooks(id_, fmt, fpath, index_is_id=True,
                        notify=True)
        current_idx = self.gui.library_view.currentIndex()
        if current_idx.isValid():
            view.model().current_changed(current_idx, current_idx)


    def add_recursive(self, single):
        root = choose_dir(self.gui, 'recursive book import root dir dialog',
                          'Select root folder')
        if not root:
            return
        from calibre.gui2.add import Adder
        self._adder = Adder(self.gui,
                self.gui.library_view.model().db,
                self.Dispatcher(self._files_added), spare_server=self.gui.spare_server)
        self.gui.tags_view.disable_recounting = True
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
        author = None
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            raw = index.model().db.authors(index.row())
            if raw:
                authors = [a.strip().replace('|', ',') for a in raw.split(',')]
                if authors:
                    author = authors[0]
        dlg = AddEmptyBookDialog(self.gui, self.gui.library_view.model().db, author)
        if dlg.exec_() == dlg.Accepted:
            num = dlg.qty_to_add
            for x in xrange(num):
                mi = MetaInformation(_('Unknown'), dlg.selected_authors)
                self.gui.library_view.model().db.import_book(mi, [])
            self.gui.library_view.model().books_added(num)
            if hasattr(self.gui, 'db_images'):
                self.gui.db_images.reset()
            self.gui.tags_view.recount()

    def add_isbns(self, books, add_tags=[]):
        self.isbn_books = list(books)
        self.add_by_isbn_ids = set()
        self.isbn_add_tags = add_tags
        QTimer.singleShot(10, self.do_one_isbn_add)
        self.isbn_add_dialog = ProgressDialog(_('Adding'),
                _('Creating book records from ISBNs'), max=len(books),
                cancelable=False, parent=self.gui)
        self.isbn_add_dialog.exec_()

    def do_one_isbn_add(self):
        try:
            db = self.gui.library_view.model().db

            try:
                x = self.isbn_books.pop(0)
            except IndexError:
                self.gui.library_view.model().books_added(self.isbn_add_dialog.value)
                self.isbn_add_dialog.accept()
                self.gui.iactions['Edit Metadata'].download_metadata(
                    ids=self.add_by_isbn_ids, ensure_fields=frozenset(['title',
                        'authors']))
                return


            mi = MetaInformation(None)
            mi.isbn = x['isbn']
            if self.isbn_add_tags:
                mi.tags = list(self.isbn_add_tags)
            fmts = [] if x['path'] is None else [x['path']]
            self.add_by_isbn_ids.add(db.import_book(mi, fmts))
            self.isbn_add_dialog.value += 1
            QTimer.singleShot(10, self.do_one_isbn_add)
        except:
            self.isbn_add_dialog.accept()
            raise

    def files_dropped(self, paths):
        to_device = self.gui.stack.currentIndex() != 0
        self._add_books(paths, to_device)

    def remote_file_dropped_on_book(self, url, fname):
        if self.gui.current_view() is not self.gui.library_view:
            return
        db = self.gui.library_view.model().db
        current_idx = self.gui.library_view.currentIndex()
        if not current_idx.isValid(): return
        cid = db.id(current_idx.row())
        from calibre.gui2.dnd import DownloadDialog
        d = DownloadDialog(url, fname, self.gui)
        d.start_download()
        if d.err is None:
            self.files_dropped_on_book(None, [d.fpath], cid=cid)

    def files_dropped_on_book(self, event, paths, cid=None):
        accept = False
        if self.gui.current_view() is not self.gui.library_view:
            return
        db = self.gui.library_view.model().db
        cover_changed = False
        current_idx = self.gui.library_view.currentIndex()
        if cid is None:
            if not current_idx.isValid(): return
            cid = db.id(current_idx.row()) if cid is None else cid
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
                    cover_changed = True
            elif ext in BOOK_EXTENSIONS:
                db.add_format_with_hooks(cid, ext, path, index_is_id=True)
                accept = True
        if accept and event is not None:
            event.accept()
        if current_idx.isValid():
            self.gui.library_view.model().current_changed(current_idx, current_idx)
        if cover_changed:
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()

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
            self.add_isbns(d.books, add_tags=d.set_tags)

    def add_books(self, *args):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        filters = get_filters()
        to_device = self.gui.stack.currentIndex() != 0
        if to_device:
            fmts = self.gui.device_manager.device.settings().format_map
            filters = [(_('Supported books'), fmts)]

        books = choose_files(self.gui, 'add books dialog dir',
                _('Select books'), filters=filters)
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
        self.gui.tags_view.disable_recounting = True
        self._adder.add(paths)

    def _files_added(self, paths=[], names=[], infos=[], on_card=None):
        self.gui.tags_view.disable_recounting = False
        if paths:
            self.gui.upload_books(paths,
                                list(map(ascii_filename, names)),
                                infos, on_card=on_card)
            self.gui.status_bar.show_message(
                    _('Uploading books to device.'), 2000)
        if getattr(self._adder, 'number_of_books_added', 0) > 0:
            self.gui.library_view.model().books_added(self._adder.number_of_books_added)
            self.gui.library_view.set_current_row(0)
            if hasattr(self.gui, 'db_images'):
                self.gui.db_images.reset()
            self.gui.tags_view.recount()

        if getattr(self._adder, 'merged_books', False):
            books = u'\n'.join([x if isinstance(x, unicode) else
                    x.decode(preferred_encoding, 'replace') for x in
                    self._adder.merged_books])
            info_dialog(self.gui, _('Merged some books'),
                    _('The following duplicate books were found and incoming book formats were '
                        'processed and merged into your Calibre database according to your automerge settings:'), det_msg=books, show=True)

        if getattr(self._adder, 'number_of_books_added', 0) > 0 or \
                getattr(self._adder, 'merged_books', False):
            # The formats of the current book could have changed if
            # automerge is enabled
            current_idx = self.gui.library_view.currentIndex()
            if current_idx.isValid():
                self.gui.library_view.model().current_changed(current_idx,
                        current_idx)

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
            self._adder.setParent(None)
            del self._adder
            self._adder = None

    def _add_from_device_adder(self, paths=[], names=[], infos=[],
                               on_card=None, model=None):
        self._files_added(paths, names, infos, on_card=on_card)
        # set the in-library flags, and as a consequence send the library's
        # metadata for this book to the device. This sets the uuid to the
        # correct value. Note that set_books_in_library might sync_booklists
        self.gui.set_books_in_library(booklists=[model.db], reset=True)
        self.gui.refresh_ondevice()

    def add_books_from_device(self, view, paths=None):
        backloading_err = self.gui.device_manager.device.BACKLOADING_ERROR_MESSAGE
        if backloading_err is not None:
            return error_dialog(self.gui, _('Add to library'), backloading_err,
                    show=True)
        if paths is None:
            rows = view.selectionModel().selectedRows()
            if not rows or len(rows) == 0:
                d = error_dialog(self.gui, _('Add to library'), _('No book selected'))
                d.exec_()
                return
            paths = [p for p in view.model().paths(rows) if p is not None]
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
        paths = self.gui.device_manager.device.prepare_addable_books(paths)
        from calibre.gui2.add import Adder
        self.__adder_func = partial(self._add_from_device_adder, on_card=None,
                                                    model=view.model())
        self._adder = Adder(self.gui, self.gui.library_view.model().db,
                self.Dispatcher(self.__adder_func), spare_server=self.gui.spare_server)
        self._adder.add(paths)


