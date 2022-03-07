#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from collections import defaultdict
from functools import partial
from qt.core import QApplication, QDialog, QPixmap, QTimer

from calibre import as_unicode, guess_type, prepare_string_for_xml
from calibre.constants import iswindows
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import MetaInformation, normalize_isbn
from calibre.gui2 import (
    choose_dir, choose_files, choose_files_and_remember_all_files, error_dialog,
    gprefs, info_dialog, question_dialog, warning_dialog
)
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.add_empty_book import AddEmptyBookDialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import ascii_filename, make_long_path_useable
from calibre.utils.icu import sort_key
from polyglot.builtins import iteritems, string_or_bytes


def get_filters():
    archives = ['zip', 'rar']
    return [
            (_('Books'), [x for x in BOOK_EXTENSIONS if x not in archives]),
            (_('EPUB books'), ['epub', 'kepub']),
            (_('Kindle books'), ['mobi', 'prc', 'azw', 'azw3', 'kfx', 'tpz', 'azw1', 'azw4']),
            (_('PDF books'), ['pdf', 'azw4']),
            (_('HTML books'), ['htm', 'html', 'xhtm', 'xhtml']),
            (_('LIT books'), ['lit']),
            (_('Text books'), ['txt', 'text', 'rtf', 'md', 'markdown', 'textile', 'txtz']),
            (_('Comics'), ['cbz', 'cbr', 'cbc']),
            (_('Archives'), archives),
            (_('Wordprocessor files'), ['odt', 'doc', 'docx']),
    ]


class AddAction(InterfaceAction):

    name = 'Add Books'
    action_spec = (_('Add books'), 'add_book.png',
            _('Add books to the calibre library/device from files on your computer')
            , _('A'))
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Add books from a single folder')

    def genesis(self):
        self._add_filesystem_book = self.Dispatcher(self.__add_filesystem_book)
        self.add_menu = self.qaction.menu()
        ma = partial(self.create_menu_action, self.add_menu)
        ma('recursive-add', _('Add from folders and sub-folders'), icon='mimetypes/dir.png').triggered.connect(self.add_recursive_question)
        ma('archive-add-book', _('Add multiple books from archive (ZIP/RAR)'), icon='mimetypes/zip.png').triggered.connect(self.add_from_archive)
        self.add_menu.addSeparator()
        ma('add-empty', _('Add empty book (Book entry with no formats)'),
                shortcut='Shift+Ctrl+E').triggered.connect(self.add_empty)
        ma('add-isbn', _('Add from ISBN'), icon='identifiers.png').triggered.connect(self.add_from_isbn)
        self.add_menu.addSeparator()
        ma('add-formats', _('Add files to selected book records'),
                triggered=self.add_formats, shortcut='Shift+A')
        ma('add-formats-clipboard', _('Add files to selected book records from clipboard'),
                triggered=self.add_formats_from_clipboard, shortcut='Shift+Alt+A', icon='edit-paste.png')
        ma('add-empty-format-to-books', _(
            'Add an empty file to selected book records')).triggered.connect(self.add_empty_format_choose)
        self.add_menu.addSeparator()
        ma('add-config', _('Control the adding of books'), icon='config.png',
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

    def _check_add_formats_ok(self):
        if self.gui.current_view() is not self.gui.library_view:
            return []
        view = self.gui.library_view
        rows = view.selectionModel().selectedRows()
        if not rows:
            error_dialog(self.gui, _('No books selected'),
                    _('Cannot add files as no books are selected'), show=True)
        ids = [view.model().id(r) for r in rows]
        return ids

    def add_formats_from_clipboard(self):
        ids = self._check_add_formats_ok()
        if not ids:
            return
        md = QApplication.instance().clipboard().mimeData()
        files_to_add = []
        images = []
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if os.access(path, os.R_OK):
                        mt = guess_type(path)[0]
                        if mt and mt.startswith('image/'):
                            images.append(path)
                        else:
                            files_to_add.append(path)
        if not files_to_add and not images:
            return error_dialog(self.gui, _('No files in clipboard'),
                    _('No files have been copied to the clipboard'), show=True)
        if files_to_add:
            self._add_formats(files_to_add, ids)
        if images:
            if len(ids) > 1 and not question_dialog(
                    self.gui,
                    _('Are you sure?'),
                    _('Are you sure you want to set the same'
                    ' cover for all %d books?')%len(ids)):
                return
            with lopen(images[0], 'rb') as f:
                cdata = f.read()
            self.gui.current_db.new_api.set_cover({book_id: cdata for book_id in ids})
            self.gui.refresh_cover_browser()
            m = self.gui.library_view.model()
            current = self.gui.library_view.currentIndex()
            m.current_changed(current, current)

    def add_formats(self, *args):
        ids = self._check_add_formats_ok()
        if not ids:
            return
        books = choose_files_and_remember_all_files(self.gui, 'add formats dialog dir',
                _('Select book files'), filters=get_filters())
        if books:
            self._add_formats(books, ids)

    def _add_formats(self, paths, ids):
        if len(ids) > 1 and not question_dialog(
                self.gui,
                _('Are you sure?'),
                _('Are you sure you want to add the same'
                  ' files to all %d books? If the format'
                  ' already exists for a book, it will be replaced.')%len(ids)):
            return
        paths = list(map(make_long_path_useable, paths))

        db = self.gui.current_db
        if len(ids) == 1:
            formats = db.formats(ids[0], index_is_id=True)
            if formats:
                formats = {x.upper() for x in formats.split(',')}
                nformats = {f.rpartition('.')[-1].upper() for f in paths}
                override = formats.intersection(nformats)
                if override:
                    title = db.title(ids[0], index_is_id=True)
                    msg = ngettext(
                        'The {0} format will be replaced in the book {1}. Are you sure?',
                        'The {0} formats will be replaced in the book {1}. Are you sure?',
                        len(override)).format(', '.join(override), title)
                    if not confirm(msg, 'confirm_format_override_on_add', title=_('Are you sure?'), parent=self.gui):
                        return

        fmt_map = {os.path.splitext(fpath)[1][1:].upper():fpath for fpath in paths}

        for id_ in ids:
            for fmt, fpath in iteritems(fmt_map):
                if fmt:
                    db.add_format_with_hooks(id_, fmt, fpath, index_is_id=True,
                        notify=True)
        current_idx = self.gui.library_view.currentIndex()
        if current_idx.isValid():
            self.gui.library_view.model().current_changed(current_idx, current_idx)

    def is_ok_to_add_empty_formats(self):
        if self.gui.stack.currentIndex() != 0:
            return
        view = self.gui.library_view
        rows = view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, _('No books selected'),
                    _('Cannot add files as no books are selected'), show=True)

        ids = [view.model().id(r) for r in rows]

        if len(ids) > 1 and not question_dialog(
                self.gui,
                _('Are you sure?'),
                _('Are you sure you want to add the same'
                  ' empty file to all %d books? If the format'
                  ' already exists for a book, it will be replaced.')%len(ids)):
            return
        return True

    def add_empty_format_choose(self):
        if not self.is_ok_to_add_empty_formats():
            return
        from calibre.ebooks.oeb.polish.create import valid_empty_formats
        from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
        d = ChooseFormatDialog(self.gui, _('Choose format of empty file'), sorted(valid_empty_formats))
        if d.exec() != QDialog.DialogCode.Accepted or not d.format():
            return
        self._add_empty_format(d.format())

    def add_empty_format(self, format_):
        if not self.is_ok_to_add_empty_formats():
            return
        self._add_empty_format(format_)

    def _add_empty_format(self, format_):
        view = self.gui.library_view
        rows = view.selectionModel().selectedRows()
        ids = [view.model().id(r) for r in rows]
        db = self.gui.library_view.model().db
        if len(ids) == 1:
            formats = db.formats(ids[0], index_is_id=True)
            if formats:
                formats = {x.lower() for x in formats.split(',')}
                if format_ in formats:
                    title = db.title(ids[0], index_is_id=True)
                    msg = _('The {0} format will be replaced in the book: {1}. Are you sure?').format(
                        format_, title)
                    if not confirm(msg, 'confirm_format_override_on_add', title=_('Are you sure?'),
                                   parent=self.gui):
                        return

        for id_ in ids:
            self.add_empty_format_to_book(id_, format_)

        current_idx = self.gui.library_view.currentIndex()
        if current_idx.isValid():
            view.model().current_changed(current_idx, current_idx)

    def add_empty_format_to_book(self, book_id, fmt):
        from calibre.ebooks.oeb.polish.create import create_book
        db = self.gui.current_db
        pt = PersistentTemporaryFile(suffix='.' + fmt.lower())
        pt.close()
        try:
            mi = db.new_api.get_metadata(book_id, get_cover=False,
                                get_user_categories=False, cover_as_data=False)
            create_book(mi, pt.name, fmt=fmt.lower())
            db.add_format_with_hooks(book_id, fmt, pt.name, index_is_id=True, notify=True)
        finally:
            os.remove(pt.name)

    def add_archive(self, single):
        paths = choose_files(
            self.gui, 'recursive-archive-add', _('Choose archive file'),
            filters=[(_('Archives'), ('zip', 'rar'))], all_files=False, select_only_single_file=False)
        if paths:
            self.do_add_recursive(paths, single, list_of_archives=True)

    def add_from_archive(self):
        single = question_dialog(self.gui, _('Type of archive'), _(
            'Will the archive have a single book per internal folder?'))
        paths = choose_files(
            self.gui, 'recursive-archive-add', _('Choose archive file'),
            filters=[(_('Archives'), ('zip', 'rar'))], all_files=False, select_only_single_file=False)
        if paths:
            self.do_add_recursive(paths, single, list_of_archives=True)

    def add_recursive(self, single):
        root = choose_dir(self.gui, 'recursive book import root dir dialog',
                          _('Select root folder'))
        if not root:
            return
        lp = os.path.normcase(os.path.abspath(self.gui.current_db.library_path))
        if lp.startswith(os.path.normcase(os.path.abspath(root)) + os.pathsep):
            return error_dialog(self.gui, _('Cannot add'), _(
                'Cannot add books from the folder: %s as it contains the currently opened calibre library') % root, show=True)
        self.do_add_recursive(root, single)

    def do_add_recursive(self, root, single, list_of_archives=False):
        from calibre.gui2.add import Adder
        Adder(root, single_book_per_directory=single, db=self.gui.current_db, list_of_archives=list_of_archives,
              callback=self._files_added, parent=self.gui, pool=self.gui.spare_pool())

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

    def add_recursive_question(self):
        single =  question_dialog(self.gui, _('Multi-file books?'), _(
            'Assume all e-book files in a single folder are multiple formats of the same book?'))
        self.add_recursive(single)

    def add_empty(self, *args):
        '''
        Add an empty book item to the library. This does not import any formats
        from a book file.
        '''
        author = series = title = None
        index = self.gui.library_view.currentIndex()
        if index.isValid():
            raw = index.model().db.authors(index.row())
            if raw:
                authors = [a.strip().replace('|', ',') for a in raw.split(',')]
                if authors:
                    author = authors[0]
            series = index.model().db.series(index.row())
            title = index.model().db.title(index.row())
        dlg = AddEmptyBookDialog(self.gui, self.gui.library_view.model().db,
                                 author, series, dup_title=title)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            temp_files = []
            num = dlg.qty_to_add
            series = dlg.selected_series
            title = dlg.selected_title or _('Unknown')
            db = self.gui.library_view.model().db
            ids, orig_fmts = [], []
            if dlg.duplicate_current_book:
                origmi = db.get_metadata(index.row(), get_cover=True, cover_as_data=True)
                if dlg.copy_formats.isChecked():
                    book_id = db.id(index.row())
                    orig_fmts = tuple(db.new_api.format(book_id, fmt, as_path=True) for fmt in db.new_api.formats(book_id))

            for x in range(num):
                if dlg.duplicate_current_book:
                    mi = origmi
                else:
                    mi = MetaInformation(title, dlg.selected_authors)
                    if series:
                        mi.series = series
                        mi.series_index = db.get_next_series_num_for(series)
                fmts = []
                empty_format = gprefs.get('create_empty_format_file', '')
                if dlg.duplicate_current_book and dlg.copy_formats.isChecked():
                    fmts = orig_fmts
                elif empty_format:
                    from calibre.ebooks.oeb.polish.create import create_book
                    pt = PersistentTemporaryFile(suffix='.' + empty_format)
                    pt.close()
                    temp_files.append(pt.name)
                    create_book(mi, pt.name, fmt=empty_format)
                    fmts = [pt.name]
                ids.append(db.import_book(mi, fmts))
            for path in orig_fmts:
                os.remove(path)
            self.refresh_gui(num)
            if ids:
                ids.reverse()
                self.gui.library_view.select_rows(ids)
            for path in temp_files:
                os.remove(path)

    def check_for_existing_isbns(self, books):
        db = self.gui.current_db.new_api
        book_id_identifiers = db.all_field_for('identifiers', db.all_book_ids(tuple))
        existing_isbns = {normalize_isbn(ids.get('isbn', '')): book_id for book_id, ids in book_id_identifiers.items()}
        existing_isbns.pop('', None)
        ok = []
        duplicates = []
        for book in books:
            q = normalize_isbn(book['isbn'])
            if q and q in existing_isbns:
                duplicates.append((book, existing_isbns[q]))
            else:
                ok.append(book)
        if duplicates:
            det_msg = '\n'.join(f'{book["isbn"]}: {db.field_for("title", book_id)}' for book, book_id in duplicates)
            if question_dialog(self.gui, _('Duplicates found'), _(
                'Books with some of the specified ISBNs already exist in the calibre library.'
                ' Click "Show details" for the full list. Do you want to add them anyway?'), det_msg=det_msg
            ):
                ok += [x[0] for x in duplicates]
        return ok

    def add_isbns(self, books, add_tags=[], check_for_existing=False):
        books = list(books)
        if check_for_existing:
            books = self.check_for_existing_isbns(books)
            if not books:
                return
        self.isbn_books = books
        self.add_by_isbn_ids = set()
        self.isbn_add_tags = add_tags
        QTimer.singleShot(10, self.do_one_isbn_add)
        self.isbn_add_dialog = ProgressDialog(_('Adding'),
                _('Creating book records from ISBNs'), max=len(books),
                cancelable=False, parent=self.gui)
        self.isbn_add_dialog.exec()

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
        if not current_idx.isValid():
            return
        cid = db.id(current_idx.row())
        from calibre.gui2.dnd import DownloadDialog
        d = DownloadDialog(url, fname, self.gui)
        d.start_download()
        if d.err is None:
            self.files_dropped_on_book(None, [d.fpath], cid=cid)

    def files_dropped_on_book(self, event, paths, cid=None, do_confirm=True):
        accept = False
        if self.gui.current_view() is not self.gui.library_view:
            return
        db = self.gui.library_view.model().db
        cover_changed = False
        current_idx = self.gui.library_view.currentIndex()
        if cid is None:
            if not current_idx.isValid():
                return
            cid = db.id(current_idx.row()) if cid is None else cid
        formats = []
        from calibre.gui2.dnd import image_extensions
        image_exts = set(image_extensions()) - set(tweaks['cover_drop_exclude'])
        if iswindows:
            from calibre.gui2.add import resolve_windows_links
            paths = list(resolve_windows_links(paths, hwnd=int(self.gui.effectiveWinId())))
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext:
                ext = ext[1:]
            if ext in image_exts:
                pmap = QPixmap()
                pmap.load(path)
                if not pmap.isNull():
                    accept = True
                    db.set_cover(cid, pmap)
                    cover_changed = True
            else:
                formats.append((ext, path))
                accept = True
        if accept and event is not None:
            event.accept()
        add_as_book = False
        if do_confirm and formats:
            ok, add_as_book = confirm(
                _('You have dropped some files onto the book <b>%s</b>. This will'
                  ' add or replace the files for this book. Do you want to proceed?') % db.title(cid, index_is_id=True),
                'confirm_drop_on_book', parent=self.gui,
                extra_button=ngettext('Add as new book', 'Add as new books', len(formats)))
            if ok and add_as_book:
                add_as_book = [path for ext, path in formats]
            if not ok or add_as_book:
                formats = []
        for ext, path in formats:
            db.add_format_with_hooks(cid, ext, path, index_is_id=True)
        if current_idx.isValid():
            self.gui.library_view.model().current_changed(current_idx, current_idx)
        if cover_changed:
            self.gui.refresh_cover_browser()
        if add_as_book:
            self.files_dropped(add_as_book)

    def __add_filesystem_book(self, paths, allow_device=True):
        if isinstance(paths, string_or_bytes):
            paths = [paths]
        books = [path for path in map(os.path.abspath, paths) if os.access(path,
            os.R_OK)]

        if books:
            to_device = allow_device and self.gui.stack.currentIndex() != 0
            self._add_books(books, to_device)
            if to_device:
                self.gui.status_bar.show_message(
                        _('Uploading books to device.'), 2000)

    def add_filesystem_book(self, paths, allow_device=True):
        self._add_filesystem_book(paths, allow_device=allow_device)

    def add_from_isbn(self, *args):
        from calibre.gui2.dialogs.add_from_isbn import AddFromISBN
        d = AddFromISBN(self.gui)
        if d.exec() == QDialog.DialogCode.Accepted and d.books:
            self.add_isbns(d.books, add_tags=d.set_tags, check_for_existing=d.check_for_existing)

    def add_books(self, *args):
        '''
        Add books from the local filesystem to either the library or the device.
        '''
        filters = get_filters()
        to_device = self.gui.stack.currentIndex() != 0
        if to_device:
            fmts = self.gui.device_manager.device.settings().format_map
            filters = [(_('Supported books'), fmts)]

        books = choose_files_and_remember_all_files(self.gui, 'add books dialog dir',
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
        Adder(paths, db=None if to_device else self.gui.current_db,
              parent=self.gui, callback=partial(self._files_added, on_card=on_card), pool=self.gui.spare_pool())

    def refresh_gui(self, num, set_current_row=-1, recount=True):
        self.gui.library_view.model().books_added(num)
        if set_current_row > -1:
            self.gui.library_view.set_current_row(0)
        self.gui.refresh_cover_browser()
        if recount:
            self.gui.tags_view.recount()

    def _files_added(self, adder, on_card=None):
        if adder.items:
            paths, infos, names = [], [], []
            for mi, cover_path, format_paths in adder.items:
                mi.cover = cover_path
                paths.append(format_paths[0]), infos.append(mi)
                names.append(ascii_filename(os.path.basename(paths[-1])))
            self.gui.upload_books(paths, names, infos, on_card=on_card)
            self.gui.status_bar.show_message(
                    _('Uploading books to device.'), 2000)
            return

        if adder.number_of_books_added > 0:
            self.refresh_gui(adder.number_of_books_added, set_current_row=0)

        if adder.merged_books:
            merged = defaultdict(list)
            for title, author in adder.merged_books:
                merged[author].append(title)
            lines = []
            for author in sorted(merged, key=sort_key):
                lines.append(f'<b><i>{prepare_string_for_xml(author)}</i></b><ol style="margin-top: 0">')
                for title in sorted(merged[author]):
                    lines.append(f'<li>{prepare_string_for_xml(title)}</li>')
                lines.append('</ol>')
            pm = ngettext('The following duplicate book was found.',
                          'The following {} duplicate books were found.',
                          len(adder.merged_books)).format(len(adder.merged_books))
            info_dialog(self.gui, _('Merged some books'), pm + ' ' +
                _('Incoming book formats were processed and merged into your '
                    'calibre database according to your auto-merge '
                    'settings. Click "Show details" to see the list of merged books.'),
                    det_msg='\n'.join(lines), show=True, only_copy_details=True)

        if adder.number_of_books_added > 0 or adder.merged_books:
            # The formats of the current book could have changed if
            # automerge is enabled
            current_idx = self.gui.library_view.currentIndex()
            if current_idx.isValid():
                self.gui.library_view.model().current_changed(current_idx,
                        current_idx)

    def _add_from_device_adder(self, adder, on_card=None, model=None):
        self._files_added(adder, on_card=on_card)
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
                d.exec()
                return
            paths = [p for p in view.model().paths(rows) if p is not None]
        ve = self.gui.device_manager.device.VIRTUAL_BOOK_EXTENSIONS

        def ext(x):
            ans = os.path.splitext(x)[1]
            ans = ans[1:] if len(ans) > 1 else ans
            return ans.lower()
        remove = {p for p in paths if ext(p) in ve}
        if remove:
            paths = [p for p in paths if p not in remove]
            vmsg = getattr(self.gui.device_manager.device, 'VIRTUAL_BOOK_EXTENSION_MESSAGE', None) or _(
                'The following books are virtual and cannot be added'
                ' to the calibre library:')
            info_dialog(self.gui,  _('Not Implemented'), vmsg, '\n'.join(remove), show=True)
            if not paths:
                return
        if not paths or len(paths) == 0:
            d = error_dialog(self.gui, _('Add to library'), _('No book files found'))
            d.exec()
            return

        self.gui.device_manager.prepare_addable_books(self.Dispatcher(partial(
            self.books_prepared, view)), paths)
        self.bpd = ProgressDialog(_('Downloading books'),
                msg=_('Downloading books from device'), parent=self.gui,
                cancelable=False)
        QTimer.singleShot(1000, self.show_bpd)

    def show_bpd(self):
        if self.bpd is not None:
            self.bpd.show()

    def books_prepared(self, view, job):
        self.bpd.hide()
        self.bpd = None
        if job.exception is not None:
            self.gui.device_job_exception(job)
            return
        paths = job.result
        ok_paths = [x for x in paths if isinstance(x, string_or_bytes)]
        failed_paths = [x for x in paths if isinstance(x, tuple)]
        if failed_paths:
            if not ok_paths:
                msg = _('Could not download files from the device')
                typ = error_dialog
            else:
                msg = _('Could not download some files from the device')
                typ = warning_dialog
            det_msg = [x[0]+ '\n    ' + as_unicode(x[1]) for x in failed_paths]
            det_msg = '\n\n'.join(det_msg)
            typ(self.gui, _('Could not download files'), msg, det_msg=det_msg,
                    show=True)

        if ok_paths:
            from calibre.gui2.add import Adder
            callback = partial(self._add_from_device_adder, on_card=None, model=view.model())
            Adder(ok_paths, db=self.gui.current_db, parent=self.gui, callback=callback, pool=self.gui.spare_pool())
