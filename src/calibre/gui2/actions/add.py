#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial
from collections import defaultdict

from PyQt5.Qt import QPixmap, QTimer

from calibre import as_unicode
from calibre.gui2 import (error_dialog, choose_files, choose_dir,
        warning_dialog, info_dialog, gprefs)
from calibre.gui2.dialogs.add_empty_book import AddEmptyBookDialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.utils.config_base import tweaks
from calibre.utils.filenames import ascii_filename
from calibre.utils.icu import sort_key
from calibre.gui2.actions import InterfaceAction
from calibre.gui2 import question_dialog
from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import PersistentTemporaryFile


def get_filters():
    return [
            (_('Books'), BOOK_EXTENSIONS),
            (_('EPUB Books'), ['epub']),
            (_('LRF Books'), ['lrf']),
            (_('HTML Books'), ['htm', 'html', 'xhtm', 'xhtml']),
            (_('LIT Books'), ['lit']),
            (_('MOBI Books'), ['mobi', 'prc', 'azw', 'azw3']),
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
            'sub-directories (Multiple books per directory, assumes every '
            'ebook file is a different book)')).triggered.connect(
                    self.add_recursive_multiple)
        arm = self.add_archive_menu = self.add_menu.addMenu(_('Add multiple books from archive (ZIP/RAR)'))
        self.create_menu_action(arm, 'recursive-single-archive', _(
            'One book per directory in the archive')).triggered.connect(partial(self.add_archive, True))
        self.create_menu_action(arm, 'recursive-multiple-archive', _(
            'Multiple books per directory in the archive')).triggered.connect(partial(self.add_archive, False))
        self.add_menu.addSeparator()
        ma('add-empty', _('Add empty book (Book entry with no formats)'),
                shortcut='Shift+Ctrl+E').triggered.connect(self.add_empty)
        ma('add-isbn', _('Add from ISBN')).triggered.connect(self.add_from_isbn)
        self.add_menu.addSeparator()
        ma('add-formats', _('Add files to selected book records'),
                triggered=self.add_formats, shortcut='Shift+A')
        arm = self.add_archive_menu = self.add_menu.addMenu(_('Add an empty file to selected book records'))
        from calibre.ebooks.oeb.polish.create import valid_empty_formats
        for fmt in sorted(valid_empty_formats):
            self.create_menu_action(arm, 'add-empty-' + fmt,
                                    _('Add empty {}').format(fmt.upper())).triggered.connect(
                                         partial(self.add_empty_format, fmt))
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

        if len(ids) > 1 and not question_dialog(
                self.gui,
                _('Are you sure?'),
                _('Are you sure you want to add the same'
                  ' files to all %d books? If the format'
                  ' already exists for a book, it will be replaced.')%len(ids)):
            return

        books = choose_files(self.gui, 'add formats dialog dir',
                _('Select book files'), filters=get_filters())
        if not books:
            return

        db = view.model().db
        if len(ids) == 1:
            formats = db.formats(ids[0], index_is_id=True)
            if formats:
                formats = {x.upper() for x in formats.split(',')}
                nformats = {f.rpartition('.')[-1].upper() for f in books}
                override = formats.intersection(nformats)
                if override:
                    title = db.title(ids[0], index_is_id=True)
                    msg = ngettext(
                        'The {0} format will be replaced in the book {1}. Are you sure?',
                        'The {0} formats will be replaced in the book {1}. Are you sure?',
                        len(override)).format(', '.join(override), title)
                    if not confirm(msg, 'confirm_format_override_on_add', title=_('Are you sure?'), parent=self.gui):
                        return

        fmt_map = {os.path.splitext(fpath)[1][1:].upper():fpath for fpath in books}

        for id_ in ids:
            for fmt, fpath in fmt_map.iteritems():
                if fmt:
                    db.add_format_with_hooks(id_, fmt, fpath, index_is_id=True,
                        notify=True)
        current_idx = self.gui.library_view.currentIndex()
        if current_idx.isValid():
            view.model().current_changed(current_idx, current_idx)

    def add_empty_format(self, format_):
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

        db = self.gui.library_view.model().db
        if len(ids) == 1:
            formats = db.formats(ids[0], index_is_id=True)
            if formats:
                formats = {x.lower() for x in formats.split(',')}
                if format_ in formats:
                    title = db.title(ids[0], index_is_id=True)
                    msg = _('The {0} format will be replaced in the book {1}. Are you sure?').format(
                        format_, title)
                    if not confirm(msg, 'confirm_format_override_on_add', title=_('Are you sure?'),
                                   parent=self.gui):
                        return

        for id_ in ids:
            from calibre.ebooks.oeb.polish.create import create_book
            pt = PersistentTemporaryFile(suffix='.' + format_)
            pt.close()
            try:
                mi = db.new_api.get_metadata(id_, get_cover=False,
                                    get_user_categories=False, cover_as_data=False)
                create_book(mi, pt.name, fmt=format_)
                db.add_format_with_hooks(id_, format_, pt.name, index_is_id=True, notify=True)
            finally:
                os.remove(pt.name)

        current_idx = self.gui.library_view.currentIndex()
        if current_idx.isValid():
            view.model().current_changed(current_idx, current_idx)

    def add_archive(self, single):
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
        if dlg.exec_() == dlg.Accepted:
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

            for x in xrange(num):
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
            tuple(map(os.remove, orig_fmts))
            self.gui.library_view.model().books_added(num)
            self.gui.refresh_cover_browser()
            self.gui.tags_view.recount()
            if ids:
                ids.reverse()
                self.gui.library_view.select_rows(ids)
            for path in temp_files:
                os.remove(path)

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
        if do_confirm and formats:
            if not confirm(
                _('You have dropped some files onto the book <b>%s</b>. This will'
                  ' add or replace the files for this book. Do you want to proceed?') % db.title(cid, index_is_id=True),
                'confirm_drop_on_book', parent=self.gui):
                formats = []
        for ext, path in formats:
            db.add_format_with_hooks(cid, ext, path, index_is_id=True)
        if current_idx.isValid():
            self.gui.library_view.model().current_changed(current_idx, current_idx)
        if cover_changed:
            self.gui.refresh_cover_browser()

    def __add_filesystem_book(self, paths, allow_device=True):
        if isinstance(paths, basestring):
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
        if d.exec_() == d.Accepted and d.books:
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
        Adder(paths, db=None if to_device else self.gui.current_db,
              parent=self.gui, callback=partial(self._files_added, on_card=on_card), pool=self.gui.spare_pool())

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
            self.gui.library_view.model().books_added(adder.number_of_books_added)
            self.gui.library_view.set_current_row(0)
            self.gui.refresh_cover_browser()
            self.gui.tags_view.recount()

        if adder.merged_books:
            merged = defaultdict(list)
            for title, author in adder.merged_books:
                merged[author].append(title)
            lines = []
            for author in sorted(merged, key=sort_key):
                lines.append(author)
                for title in sorted(merged[author], key=sort_key):
                    lines.append('\t' + title)
                lines.append('')
            pm = ngettext('The following duplicate book was found.',
                          'The following {} duplicate books were found.',
                          len(adder.merged_books)).format(len(adder.merged_books))
            info_dialog(self.gui, _('Merged some books'), pm + ' ' +
                _('Incoming book formats were processed and merged into your '
                    'calibre database according to your auto-merge '
                    'settings:'),
                    det_msg='\n'.join(lines), show=True)

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
            vmsg = getattr(self.gui.device_manager.device, 'VIRTUAL_BOOK_EXTENSION_MESSAGE', None) or _(
                'The following books are virtual and cannot be added'
                ' to the calibre library:')
            info_dialog(self.gui,  _('Not Implemented'), vmsg, '\n'.join(remove), show=True)
            if not paths:
                return
        if not paths or len(paths) == 0:
            d = error_dialog(self.gui, _('Add to library'), _('No book files found'))
            d.exec_()
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
        ok_paths = [x for x in paths if isinstance(x, basestring)]
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
