#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
import os
import shutil
from contextlib import contextmanager
from functools import partial
from io import BytesIO

from qt.core import QAction, QApplication, QDialog, QIcon, QMenu, QMimeData, QModelIndex, QTimer, QUrl

from calibre.db.errors import NoSuchFormat
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf2 import OPF, metadata_to_opf
from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.gui2 import Dispatcher, error_dialog, gprefs, question_dialog
from calibre.gui2.actions import InterfaceActionWithLibraryDrop
from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.device_category_editor import DeviceCategoryEditor
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.library.comments import merge_comments
from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key
from calibre.utils.localization import ngettext
from polyglot.builtins import iteritems

DATA_FILES_ICON_NAME = 'unpack-book.png'


class EditMetadataAction(InterfaceActionWithLibraryDrop):

    name = 'Edit Metadata'
    action_spec = (_('Edit metadata'), 'edit_input.png', _('Change the title/author/cover etc. of books'), _('E'))
    action_type = 'current'
    action_add_menu = True

    def do_drop(self):
        book_ids = self.dropped_ids
        del self.dropped_ids
        if book_ids:
            db = self.gui.library_view.model().db
            rows = [db.row(i) for i in book_ids]
            self.edit_metadata_for(rows, book_ids)

    def genesis(self):
        md = self.qaction.menu()
        cm = partial(self.create_menu_action, md)
        cm('individual', _('Edit metadata individually'), icon=self.qaction.icon(),
                triggered=partial(self.edit_metadata, False, bulk=False))
        cm('bulk', _('Edit metadata in bulk'),
                triggered=partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        cm('download', _('Download metadata and covers'), icon='download-metadata.png',
                triggered=partial(self.download_metadata, ids=None),
                shortcut='Ctrl+D')
        self.metadata_menu = md

        self.metamerge_menu = mb = QMenu()
        cm2 = partial(self.create_menu_action, mb)
        cm2('merge delete', _('Merge into first selected book - delete others'),
                triggered=self.merge_books)
        mb.addSeparator()
        cm2('merge keep', _('Merge into first selected book - keep others'),
                triggered=partial(self.merge_books, safe_merge=True),
                shortcut='Alt+M')
        mb.addSeparator()
        cm2('merge formats', _('Merge only formats into first selected book - delete others'),
                triggered=partial(self.merge_books, merge_only_formats=True),
                shortcut='Alt+Shift+M')
        self.merge_menu = mb
        md.addSeparator()
        self.action_copy = cm('copy', _('Copy metadata'), icon='edit-copy.png', triggered=self.copy_metadata)
        self.action_paste = cm('paste', _('Paste metadata'), icon='edit-paste.png', triggered=self.paste_metadata)
        self.action_paste_ignore_excluded = ac = cm(
            'paste_include_excluded_fields', _('Paste metadata including excluded fields'), icon='edit-paste.png',
            triggered=self.paste_metadata_including_excluded_fields)
        ac.setVisible(False)
        self.action_merge = cm('merge', _('Merge book records'), icon='merge_books.png',
            shortcut=_('M'), triggered=self.merge_books)
        self.action_merge.setMenu(mb)
        self.action_manage_data_files = cm(
            'manage_data_files', _('Manage data files'), icon=DATA_FILES_ICON_NAME, triggered=self.manage_data_files)

        self.qaction.triggered.connect(self.edit_metadata)
        ac = QAction(_('Copy URL to show book in calibre'), self.gui)
        ac.setToolTip(_('Copy URLs to show the currently selected books in calibre, to the system clipboard'))
        ac.triggered.connect(self.copy_show_link)
        self.gui.addAction(ac)
        self.gui.keyboard.register_shortcut(
            self.unique_name + ' - ' + 'copy_show_book',
            ac.text(), description=ac.toolTip(),
            action=ac, group=self.action_spec[0])
        ac = QAction(_('Copy URL to open book in calibre'), self.gui)
        ac.triggered.connect(self.copy_view_link)
        ac.setToolTip(_('Copy URLs to open the currently selected books in calibre, to the system clipboard'))
        self.gui.addAction(ac)
        self.gui.keyboard.register_shortcut(
            self.unique_name + ' - ' + 'copy_view_book',
            ac.text(), description=ac.toolTip(),
            action=ac, group=self.action_spec[0])

    def manage_data_files(self):
        from calibre.gui2.dialogs.data_files_manager import DataFilesManager
        db = self.gui.current_db
        ids = self.gui.library_view.get_selected_ids()
        for book_id in ids:
            d = DataFilesManager(db, book_id, self.gui)
            d.exec()
        cr = self.gui.library_view.currentIndex().row()
        self.gui.library_view.model().refresh_ids(ids, cr)

    def _copy_links(self, lines):
        urls = QUrl.fromStringList(lines)
        cb = QApplication.instance().clipboard()
        md = QMimeData()
        md.setText('\n'.join(lines))
        md.setUrls(urls)
        cb.setMimeData(md)

    def copy_show_link(self):
        db = self.gui.current_db
        ids = [db.id(row.row()) for row in self.gui.library_view.selectionModel().selectedRows()]
        db = db.new_api
        library_id = getattr(db, 'server_library_id', None)
        if not library_id or not ids:
            return
        lines = [f'calibre://show-book/{library_id}/{book_id}' for book_id in ids]
        self._copy_links(lines)

    def copy_view_link(self):
        from calibre.gui2.actions.view import preferred_format
        db = self.gui.current_db
        ids = [db.id(row.row()) for row in self.gui.library_view.selectionModel().selectedRows()]
        db = db.new_api
        library_id = getattr(db, 'server_library_id', None)
        if not library_id or not ids:
            return
        lines = []
        for book_id in ids:
            formats = db.new_api.formats(book_id, verify_formats=True)
            if formats:
                fmt = preferred_format(formats)
                lines.append(f'calibre://view-book/{library_id}/{book_id}/{fmt}')
        if lines:
            self._copy_links(lines)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
        for action in self.metamerge_menu.actions() + self.metadata_menu.actions():
            action.setEnabled(enabled)

    def copy_metadata(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot copy metadata'),
                                _('No books selected'), show=True)
        if len(rows) > 1:
            return error_dialog(self.gui, _('Cannot copy metadata'),
                                _('Multiple books selected, can only copy from one book at a time.'), show=True)
        db = self.gui.current_db
        book_id = db.id(rows[0].row())
        mi = db.new_api.get_metadata(book_id)
        md = QMimeData()
        md.setText(str(mi))
        md.setData('application/calibre-book-metadata', bytearray(metadata_to_opf(mi, default_lang='und')))
        img = db.new_api.cover(book_id, as_image=True)
        if img:
            md.setImageData(img)
        c = QApplication.clipboard()
        c.setMimeData(md)

    def paste_metadata(self):
        self.do_paste()

    def paste_metadata_including_excluded_fields(self):
        self.do_paste(ignore_excluded_fields=True)

    def do_paste(self, ignore_excluded_fields=False):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot paste metadata'),
                                _('No books selected'), show=True)
        c = QApplication.clipboard()
        md = c.mimeData()
        if not md.hasFormat('application/calibre-book-metadata'):
            return error_dialog(self.gui, _('Cannot paste metadata'),
                                _('No copied metadata available'), show=True)
        if len(rows) > 1:
            if not confirm(_(
                    'You are pasting metadata onto <b>multiple books</b> ({num_of_books}). Are you'
                    ' sure you want to do that?').format(num_of_books=len(rows)), 'paste-onto-multiple', parent=self.gui):
                return
        data = bytes(md.data('application/calibre-book-metadata'))
        mi = OPF(BytesIO(data), populate_spine=False, read_toc=False, try_to_guess_cover=False).to_book_metadata()
        mi.application_id = mi.uuid_id = None
        if ignore_excluded_fields:
            exclude = set()
        else:
            exclude = set(tweaks['exclude_fields_on_paste'])
        paste_cover = 'cover' not in exclude
        cover = md.imageData() if paste_cover else None
        exclude.discard('cover')
        for field in exclude:
            mi.set_null(field)
        db = self.gui.current_db
        book_ids = {db.id(r.row()) for r in rows}
        title_excluded = 'title' in exclude
        authors_excluded = 'authors' in exclude
        for book_id in book_ids:
            if title_excluded:
                mi.title = db.new_api.field_for('title', book_id)
            if authors_excluded:
                mi.authors = db.new_api.field_for('authors', book_id)
            db.new_api.set_metadata(book_id, mi, ignore_errors=True)
        if cover:
            db.new_api.set_cover({book_id: cover for book_id in book_ids})
        self.refresh_books_after_metadata_edit(book_ids)

    # Download metadata {{{
    def download_metadata(self, ids=None, ensure_fields=None):
        if ids is None:
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) == 0:
                return error_dialog(self.gui, _('Cannot download metadata'),
                            _('No books selected'), show=True)
            db = self.gui.library_view.model().db
            ids = [db.id(row.row()) for row in rows]
        from calibre.ebooks.metadata.sources.update import update_sources
        from calibre.gui2.metadata.bulk_download import start_download
        update_sources()
        start_download(self.gui, ids,
                Dispatcher(self.metadata_downloaded),
                ensure_fields=ensure_fields)

    def cleanup_bulk_download(self, tdir, *args):
        try:
            shutil.rmtree(tdir, ignore_errors=True)
        except:
            pass

    def metadata_downloaded(self, job):
        if job.failed:
            self.gui.job_exception(job, dialog_title=_('Failed to download metadata'))
            return
        from calibre.gui2.metadata.bulk_download import get_job_details
        (aborted, id_map, tdir, log_file, failed_ids, failed_covers, all_failed,
                det_msg, lm_map) = get_job_details(job)
        if aborted:
            return self.cleanup_bulk_download(tdir)
        if all_failed:
            num = len(failed_ids | failed_covers)
            self.cleanup_bulk_download(tdir)
            return error_dialog(self.gui, _('Download failed'), ngettext(
                'Failed to download metadata or cover for the selected book.',
                'Failed to download metadata or covers for any of the {} books.', num
            ).format(num), det_msg=det_msg, show=True)

        self.gui.status_bar.show_message(_('Metadata download completed'), 3000)

        msg = '<p>' + ngettext(
            'Finished downloading metadata for the selected book.',
            'Finished downloading metadata for <b>{} books</b>.', len(id_map)).format(len(id_map)) + ' ' + \
            _('Proceed with updating the metadata in your library?')

        show_copy_button = False
        checkbox_msg = None
        if failed_ids or failed_covers:
            show_copy_button = True
            num = len(failed_ids.union(failed_covers))
            msg += '<p>'+_('Could not download metadata and/or covers for %d of the books. Click'
                    ' "Show details" to see which books.')%num
            checkbox_msg = _('Show the &failed books in the main book list '
                    'after updating metadata')

        if getattr(job, 'metadata_and_covers', None) == (False, True):
            # Only covers, remove failed cover downloads from id_map
            for book_id in failed_covers:
                if hasattr(id_map, 'discard'):
                    id_map.discard(book_id)
        payload = (id_map, tdir, log_file, lm_map,
                failed_ids.union(failed_covers))
        review_apply = partial(self.apply_downloaded_metadata, True)
        normal_apply = partial(self.apply_downloaded_metadata, False)
        self.gui.proceed_question(
            normal_apply, payload, log_file, _('Download log'),
            _('Metadata download complete'), msg, icon='download-metadata.png',
            det_msg=det_msg, show_copy_button=show_copy_button,
            cancel_callback=partial(self.cleanup_bulk_download, tdir),
            log_is_file=True, checkbox_msg=checkbox_msg,
            checkbox_checked=False, action_callback=review_apply,
            action_label=_('Revie&w downloaded metadata'),
            action_icon=QIcon.ic('auto_author_sort.png'))

    def apply_downloaded_metadata(self, review, payload, *args):
        good_ids, tdir, log_file, lm_map, failed_ids = payload
        if not good_ids:
            return
        restrict_to_failed = False

        modified = set()
        db = self.gui.current_db

        for i in good_ids:
            lm = db.metadata_last_modified(i, index_is_id=True)
            if lm is not None and lm_map[i] is not None and lm > lm_map[i]:
                title = db.title(i, index_is_id=True)
                authors = db.authors(i, index_is_id=True)
                if authors:
                    authors = [x.replace('|', ',') for x in authors.split(',')]
                    title += ' - ' + authors_to_string(authors)
                modified.add(title)

        if modified:
            from calibre.utils.icu import lower

            modified = sorted(modified, key=lower)
            if not question_dialog(self.gui, _('Some books changed'), '<p>' + _(
                'The metadata for some books in your library has'
                ' changed since you started the download. If you'
                ' proceed, some of those changes may be overwritten. '
                'Click "Show details" to see the list of changed books. '
                'Do you want to proceed?'), det_msg='\n'.join(modified)):
                return

        id_map = {}
        for bid in good_ids:
            opf = os.path.join(tdir, '%d.mi'%bid)
            if not os.path.exists(opf):
                opf = None
            cov = os.path.join(tdir, '%d.cover'%bid)
            if not os.path.exists(cov):
                cov = None
            id_map[bid] = (opf, cov)

        if review:
            def get_metadata(book_id):
                oldmi = db.get_metadata(book_id, index_is_id=True, get_cover=True, cover_as_data=True)
                opf, cov = id_map[book_id]
                if opf is None:
                    newmi = Metadata(oldmi.title, authors=tuple(oldmi.authors))
                else:
                    with open(opf, 'rb') as f:
                        newmi = OPF(f, basedir=os.path.dirname(opf), populate_spine=False).to_book_metadata()
                        newmi.cover, newmi.cover_data = None, (None, None)
                        for x in ('title', 'authors'):
                            if newmi.is_null(x):
                                # Title and author are set to null if they are
                                # the same as the originals as an optimization,
                                # we undo that, as it is confusing.
                                newmi.set(x, copy.copy(oldmi.get(x)))
                if cov:
                    with open(cov, 'rb') as f:
                        newmi.cover_data = ('jpg', f.read())
                return oldmi, newmi
            from calibre.gui2.metadata.diff import CompareMany
            d = CompareMany(
                set(id_map), get_metadata, db.field_metadata, parent=self.gui,
                window_title=_('Review downloaded metadata'),
                reject_button_tooltip=_('Discard downloaded metadata for this book'),
                accept_all_tooltip=_('Use the downloaded metadata for all remaining books'),
                reject_all_tooltip=_('Discard downloaded metadata for all remaining books'),
                revert_tooltip=_('Discard the downloaded value for: %s'),
                intro_msg=_('The downloaded metadata is on the left and the original metadata'
                            ' is on the right. If a downloaded value is blank or unknown,'
                            ' the original value is used.'),
                action_button=(_('&View book'), 'view.png', self.gui.iactions['View'].view_historical),
                db=db
            )
            if d.exec() == QDialog.DialogCode.Accepted:
                if d.mark_rejected:
                    failed_ids |= d.rejected_ids
                    restrict_to_failed = True
                nid_map = {}
                for book_id, (changed, mi) in iteritems(d.accepted):
                    if mi is None:  # discarded
                        continue
                    if changed:
                        opf, cov = id_map[book_id]
                        cfile = mi.cover
                        mi.cover, mi.cover_data = None, (None, None)
                        if opf is not None:
                            with open(opf, 'wb') as f:
                                f.write(metadata_to_opf(mi))
                        if cfile and cov:
                            shutil.copyfile(cfile, cov)
                            os.remove(cfile)
                    nid_map[book_id] = id_map[book_id]
                id_map = nid_map
            else:
                id_map = {}

        restrict_to_failed = restrict_to_failed or bool(args and args[0])
        restrict_to_failed = restrict_to_failed and bool(failed_ids)
        if restrict_to_failed:
            db.data.set_marked_ids(failed_ids)

        self.apply_metadata_changes(
            id_map, merge_comments=msprefs['append_comments'], icon='download-metadata.png',
            callback=partial(self.downloaded_metadata_applied, tdir, restrict_to_failed))

    def downloaded_metadata_applied(self, tdir, restrict_to_failed, *args):
        if restrict_to_failed:
            self.gui.search.set_search_string('marked:true')
        self.cleanup_bulk_download(tdir)

    # }}}

    def edit_metadata(self, checked, bulk=None):
        '''
        Edit metadata of selected books in library.
        '''
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit metadata'),
                             _('No books selected'))
            d.exec()
            return
        row_list = [r.row() for r in rows]
        m = self.gui.library_view.model()
        ids = [m.id(r) for r in rows]
        self.edit_metadata_for(row_list, ids, bulk=bulk)

    def edit_metadata_for(self, rows, book_ids, bulk=None):
        previous = self.gui.library_view.currentIndex()
        if bulk or (bulk is None and len(rows) > 1):
            return self.do_edit_bulk_metadata(rows, book_ids)

        current_row = 0
        row_list = rows
        editing_multiple = len(row_list) > 1

        if not editing_multiple:
            cr = row_list[0]
            row_list = \
                list(range(self.gui.library_view.model().rowCount(QModelIndex())))
            current_row = row_list.index(cr)

        view = self.gui.library_view.alternate_views.current_view
        try:
            hpos = view.horizontalScrollBar().value()
        except Exception:
            hpos = 0

        changed, rows_to_refresh = self.do_edit_metadata(row_list, current_row, editing_multiple)

        m = self.gui.library_view.model()

        if rows_to_refresh:
            m.refresh_rows(rows_to_refresh)

        if changed:
            self.refresh_books_after_metadata_edit(changed, previous)
        if self.gui.library_view.alternate_views.current_view is view:
            if hasattr(view, 'restore_hpos'):
                view.restore_hpos(hpos)
            else:
                view.horizontalScrollBar().setValue(hpos)

    def refresh_books_after_metadata_edit(self, book_ids, previous=None):
        m = self.gui.library_view.model()
        m.refresh_ids(list(book_ids))
        current = self.gui.library_view.currentIndex()
        self.gui.refresh_cover_browser()
        m.current_changed(current, previous or current)
        self.gui.tags_view.recount_with_position_based_index()
        qv = get_quickview_action_plugin()
        if qv:
            qv.refresh_quickview(current)

    def do_edit_metadata(self, row_list, current_row, editing_multiple):
        from calibre.gui2.metadata.single import edit_metadata
        db = self.gui.library_view.model().db
        parent = getattr(self, 'override_parent', None) or self.gui
        changed, rows_to_refresh = edit_metadata(db, row_list, current_row,
                parent=parent, view_slot=self.view_format_callback,
                edit_slot=self.edit_format_callback,
                set_current_callback=self.set_current_callback, editing_multiple=editing_multiple)
        return changed, rows_to_refresh

    @contextmanager
    def different_parent(self, parent):
        orig = getattr(self, 'override_parent', None)
        self.override_parent = parent
        try:
            yield
        finally:
            self.override_parent = orig

    def set_current_callback(self, id_):
        db = self.gui.library_view.model().db
        current_row = db.row(id_)
        self.gui.library_view.set_current_row(current_row)
        self.gui.library_view.scroll_to_row(current_row)

    def view_format_callback(self, id_, fmt):
        view = self.gui.iactions['View']
        if id_ is None:
            view._view_file(fmt)
        else:
            view.view_format_by_id(id_, fmt)

    def edit_format_callback(self, id_, fmt):
        edit = self.gui.iactions['Tweak ePub']
        edit.ebook_edit_format(id_, fmt)

    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        m = self.gui.library_view.model()
        ids = [m.id(r) for r in rows]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit metadata'),
                    _('No books selected'))
            d.exec()
            return
        self.do_edit_bulk_metadata(rows, ids)

    def do_edit_bulk_metadata(self, rows, book_ids):
        # Prevent the TagView from updating due to signals from the database
        self.gui.tags_view.blockSignals(True)
        changed = False
        refresh_books = set(book_ids)
        try:
            current_tab = -1
            while True:
                dialog = MetadataBulkDialog(self.gui, rows,
                                self.gui.library_view.model(), current_tab, refresh_books)
                if dialog.changed:
                    changed = True
                if not dialog.do_again:
                    break
                current_tab = dialog.central_widget.currentIndex()
        finally:
            self.gui.tags_view.blockSignals(False)
        if changed:
            refresh_books |= dialog.refresh_books
            m = self.gui.library_view.model()
            if gprefs['refresh_book_list_on_bulk_edit']:
                m.refresh(reset=False)
                m.research()
            else:
                m.refresh_ids(refresh_books)
            self.gui.tags_view.recount()
            self.gui.refresh_cover_browser()
            self.gui.library_view.select_rows(book_ids)

    # Merge books {{{

    def confirm_large_merge(self, num):
        if num < 5:
            return True
        return confirm('<p>'+_(
            'You are about to merge very many ({}) books. '
            'Are you <b>sure</b> you want to proceed?').format(num) + '</p>',
            'merge_too_many_books', self.gui)

    def books_dropped(self, merge_map):
        covers_replaced = False
        for dest_id, src_ids in iteritems(merge_map):
            if not self.confirm_large_merge(len(src_ids) + 1):
                continue
            from calibre.gui2.dialogs.confirm_merge import merge_drop
            d = merge_drop(dest_id, src_ids, self.gui)
            if d is None:
                return
            if d.merge_formats:
                self.add_formats(dest_id, self.formats_for_ids(list(src_ids)))
            if d.merge_metadata:
                self.merge_metadata(dest_id, src_ids, replace_cover=d.replace_cover, save_alternate_cover=d.save_alternate_cover)
                if d.replace_cover:
                    covers_replaced = True
            if d.delete_books:
                self.delete_books_after_merge(src_ids)
            # leave the selection highlight on the target book
            row = self.gui.library_view.ids_to_rows([dest_id])[dest_id]
            self.gui.library_view.set_current_row(row)
            if covers_replaced:
                self.gui.refresh_cover_browser()

    def merge_books(self, safe_merge=False, merge_only_formats=False):
        '''
        Merge selected books in library.
        '''
        from calibre.gui2.dialogs.confirm_merge import confirm_merge
        if self.gui.current_view() is not self.gui.library_view:
            return
        rows = self.gui.library_view.indices_for_merge()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot merge books'),
                                _('No books selected'), show=True)
        if len(rows) < 2:
            return error_dialog(self.gui, _('Cannot merge books'),
                        _('At least two books must be selected for merging'),
                        show=True)
        if not self.confirm_large_merge(len(rows)):
            return

        dest_id, src_ids = self.books_to_merge(rows)
        mi = self.gui.current_db.new_api.get_proxy_metadata(dest_id)
        title = mi.title
        hpos = self.gui.library_view.horizontalScrollBar().value()
        if safe_merge:
            confirmed, save_alternate_cover = confirm_merge('<p>'+_(
                'Book formats and metadata from the selected books '
                'will be added to the <b>first selected book</b> (%s).<br> '
                'The second and subsequently selected books will not '
                'be deleted or changed.<br><br>'
                'Please confirm you want to proceed.')%title + '</p>',
                'merge_books_safe', self.gui, mi, ask_about_save_alternate_cover=True)
            if not confirmed:
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.merge_metadata(dest_id, src_ids, save_alternate_cover=save_alternate_cover)
        elif merge_only_formats:
            if not confirm_merge('<p>'+_(
                'Book formats from the selected books will be merged '
                'into the <b>first selected book</b> (%s). '
                'Metadata in the first selected book will not be changed. '
                'Author, Title and all other metadata will <i>not</i> be merged.<br><br>'
                'After being merged, the second and subsequently '
                'selected books, with any metadata they have will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title + '</p>',
                'merge_only_formats', self.gui, mi)[0]:
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.delete_books_after_merge(src_ids)
        else:
            confirmed, save_alternate_cover = confirm_merge('<p>'+_(
                'Book formats and metadata from the selected books will be merged '
                'into the <b>first selected book</b> (%s).<br><br>'
                'After being merged, the second and '
                'subsequently selected books will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title + '</p>',
                'merge_books', self.gui, mi, ask_about_save_alternate_cover=True)
            if not confirmed:
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.merge_metadata(dest_id, src_ids, save_alternate_cover=save_alternate_cover)
            self.merge_data_files(dest_id, src_ids)
            self.delete_books_after_merge(src_ids)
            # leave the selection highlight on first selected book
            dest_row = rows[0].row()
            for row in rows:
                if row.row() < rows[0].row():
                    dest_row -= 1
            self.gui.library_view.set_current_row(dest_row)
        cr = self.gui.library_view.currentIndex().row()
        self.gui.library_view.model().refresh_ids((dest_id,), cr)
        self.gui.library_view.horizontalScrollBar().setValue(hpos)

    def merge_data_files(self, dest_id, src_ids):
        self.gui.current_db.new_api.merge_extra_files(dest_id, src_ids)

    def add_formats(self, dest_id, src_books, replace=False):
        for src_book in src_books:
            if src_book:
                fmt = os.path.splitext(src_book)[-1].replace('.', '').upper()
                with open(src_book, 'rb') as f:
                    self.gui.library_view.model().db.add_format(dest_id, fmt, f, index_is_id=True,
                            notify=False, replace=replace)

    def formats_for_ids(self, ids):
        m = self.gui.library_view.model()
        ans = []
        for id_ in ids:
            dbfmts = m.db.formats(id_, index_is_id=True)
            if dbfmts:
                for fmt in dbfmts.split(','):
                    try:
                        path = m.db.format(id_, fmt, index_is_id=True,
                                as_path=True)
                        ans.append(path)
                    except NoSuchFormat:
                        continue
        return ans

    def formats_for_books(self, rows):
        m = self.gui.library_view.model()
        return self.formats_for_ids(list(map(m.id, rows)))

    def books_to_merge(self, rows):
        src_ids = []
        m = self.gui.library_view.model()
        for i, row in enumerate(rows):
            id_ = m.id(row)
            if i == 0:
                dest_id = id_
            else:
                src_ids.append(id_)
        return [dest_id, src_ids]

    def delete_books_after_merge(self, ids_to_delete):
        self.gui.library_view.model().delete_books_by_id(ids_to_delete)

    def merge_metadata(self, dest_id, src_ids, replace_cover=False, save_alternate_cover=False):
        self.gui.current_db.new_api.merge_book_metadata(dest_id, src_ids, replace_cover, save_alternate_cover=save_alternate_cover)
    # }}}

    def edit_device_collections(self, view, oncard=None):
        model = view.model()
        result = model.get_collections_with_ids()
        d = DeviceCategoryEditor(self.gui, tag_to_match=None, data=result, key=sort_key)
        d.exec()
        if d.result() == QDialog.DialogCode.Accepted:
            to_rename = d.to_rename  # dict of new text to old ids
            to_delete = d.to_delete  # list of ids
            for old_id, new_name in iteritems(to_rename):
                model.rename_collection(old_id, new_name=str(new_name))
            for item in to_delete:
                model.delete_collection_using_id(item)
            self.gui.upload_collections(model.db, view=view, oncard=oncard)
            view.reset()

    # Apply bulk metadata changes {{{
    def apply_metadata_changes(self, id_map, title=None, msg='', callback=None,
            merge_tags=True, merge_comments=False, icon=None):
        '''
        Apply the metadata changes in id_map to the database synchronously
        id_map must be a mapping of ids to Metadata objects. Set any fields you
        do not want updated in the Metadata object to null. An easy way to do
        that is to create a metadata object as Metadata(_('Unknown')) and then
        only set the fields you want changed on this object.

        callback can be either None or a function accepting a single argument,
        in which case it is called after applying is complete with the list of
        changed ids.

        id_map can also be a mapping of ids to 2-tuple's where each 2-tuple
        contains the absolute paths to an OPF and cover file respectively. If
        either of the paths is None, then the corresponding metadata is not
        updated.
        '''
        if title is None:
            title = _('Applying changed metadata')
        self.apply_id_map = list(iteritems(id_map))
        self.apply_current_idx = 0
        self.apply_failures = []
        self.applied_ids = set()
        self.apply_pd = None
        self.apply_callback = callback
        if len(self.apply_id_map) > 1:
            from calibre.gui2.dialogs.progress import ProgressDialog
            self.apply_pd = ProgressDialog(title, msg, min=0,
                    max=len(self.apply_id_map)-1, parent=self.gui,
                    cancelable=False, icon=icon)
            self.apply_pd.setModal(True)
            self.apply_pd.show()
        self._am_merge_tags = merge_tags
        self._am_merge_comments = merge_comments
        self.do_one_apply()

    def do_one_apply(self):
        if self.apply_current_idx >= len(self.apply_id_map):
            return self.finalize_apply()

        i, mi = self.apply_id_map[self.apply_current_idx]
        if self.gui.current_db.has_id(i):
            if isinstance(mi, tuple):
                opf, cover = mi
                if opf:
                    mi = OPF(open(opf, 'rb'), basedir=os.path.dirname(opf),
                            populate_spine=False).to_book_metadata()
                    self.apply_mi(i, mi)
                if cover:
                    self.gui.current_db.set_cover(i, open(cover, 'rb'),
                            notify=False, commit=False)
                    self.applied_ids.add(i)
            else:
                self.apply_mi(i, mi)

        self.apply_current_idx += 1
        if self.apply_pd is not None:
            self.apply_pd.value += 1
        QTimer.singleShot(5, self.do_one_apply)

    def apply_mi(self, book_id, mi):
        db = self.gui.current_db

        try:
            set_title = not mi.is_null('title')
            set_authors = not mi.is_null('authors')
            idents = db.get_identifiers(book_id, index_is_id=True)
            if mi.identifiers:
                idents.update(mi.identifiers)
            mi.identifiers = idents
            if mi.is_null('series'):
                mi.series_index = None
            if self._am_merge_tags:
                old_tags = db.tags(book_id, index_is_id=True)
                if old_tags:
                    tags = [x.strip() for x in old_tags.split(',')] + (
                            mi.tags if mi.tags else [])
                    mi.tags = list(set(tags))
            if self._am_merge_comments:
                old_comments = db.new_api.field_for('comments', book_id)
                if old_comments and mi.comments and old_comments != mi.comments:
                    mi.comments = merge_comments(old_comments, mi.comments)
            db.set_metadata(book_id, mi, commit=False, set_title=set_title,
                    set_authors=set_authors, notify=False)
            self.applied_ids.add(book_id)
        except:
            import traceback
            self.apply_failures.append((book_id, traceback.format_exc()))

        try:
            if mi.cover:
                os.remove(mi.cover)
        except:
            pass

    def finalize_apply(self):
        db = self.gui.current_db
        db.commit()

        if self.apply_pd is not None:
            self.apply_pd.hide()

        if self.apply_failures:
            msg = []
            for i, tb in self.apply_failures:
                title = db.title(i, index_is_id=True)
                authors = db.authors(i, index_is_id=True)
                if authors:
                    authors = [x.replace('|', ',') for x in authors.split(',')]
                    title += ' - ' + authors_to_string(authors)
                msg.append(title+'\n\n'+tb+'\n'+('*'*80))

            error_dialog(self.gui, _('Some failures'),
                _('Failed to apply updated metadata for some books'
                    ' in your library. Click "Show details" to see '
                    'details.'), det_msg='\n\n'.join(msg), show=True)
        changed_books = len(self.applied_ids or ())
        self.refresh_gui(self.applied_ids)

        self.apply_id_map = []
        self.apply_pd = None
        try:
            if callable(self.apply_callback):
                self.apply_callback(list(self.applied_ids))
        finally:
            self.apply_callback = None
        if changed_books:
            QApplication.alert(self.gui, 2000)

    def refresh_gui(self, book_ids, covers_changed=True, tag_browser_changed=True):
        if book_ids:
            cr = self.gui.library_view.currentIndex().row()
            self.gui.library_view.model().refresh_ids(
                list(book_ids), cr)
            if covers_changed:
                self.gui.refresh_cover_browser()
            if tag_browser_changed:
                self.gui.tags_view.recount()

    # }}}

    def remove_metadata_item(self, book_id, field, value):
        db = self.gui.current_db.new_api
        fm = db.field_metadata[field]
        affected_books = set()
        if field == 'identifiers':
            identifiers = db.field_for(field, book_id)
            if identifiers.pop(value, False) is not False:
                affected_books = db.set_field(field, {book_id:identifiers})
        elif field == 'authors':
            authors = db.field_for(field, book_id)
            new_authors = [x for x in authors if x != value] or [_('Unknown')]
            if new_authors != authors:
                affected_books = db.set_field(field, {book_id:new_authors})
        elif fm['is_multiple']:
            item_id = db.get_item_id(field, value)
            if item_id is not None:
                affected_books = db.remove_items(field, (item_id,), {book_id})
        else:
            affected_books = db.set_field(field, {book_id:''})
        if affected_books:
            self.refresh_books_after_metadata_edit(affected_books)

    def set_cover_from_format(self, book_id, fmt):
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.utils.config import prefs
        fmt = fmt.lower()
        cdata = None
        db = self.gui.current_db.new_api
        if fmt in ('pdf', 'cbz', 'cbr'):
            path = db.format_abspath(book_id, fmt)
            if path is None:
                return error_dialog(self.gui, _('Format file missing'), _(
                    'Cannot read cover as the %s file is missing from this book') % fmt.upper(), show=True)
            from calibre.gui2.metadata.pdf_covers import PDFCovers
            d = PDFCovers(path, parent=self.gui)
            ret = d.exec()
            if ret == QDialog.DialogCode.Accepted:
                cpath = d.cover_path
                if cpath:
                    with open(cpath, 'rb') as f:
                        cdata = f.read()
            d.cleanup()
            if ret != QDialog.DialogCode.Accepted:
                return
        else:
            stream = BytesIO()
            try:
                db.copy_format_to(book_id, fmt, stream)
            except NoSuchFormat:
                return error_dialog(self.gui, _('Format file missing'), _(
                    'Cannot read cover as the %s file is missing from this book') % fmt.upper(), show=True)
            old = prefs['read_file_metadata']
            if not old:
                prefs['read_file_metadata'] = True
            try:
                stream.seek(0)
                mi = get_metadata(stream, fmt)
            except Exception:
                import traceback
                return error_dialog(self.gui, _('Could not read metadata'),
                            _('Could not read metadata from %s format')%fmt.upper(),
                             det_msg=traceback.format_exc(), show=True)
            finally:
                if old != prefs['read_file_metadata']:
                    prefs['read_file_metadata'] = old
            if mi.cover and os.access(mi.cover, os.R_OK):
                with open(mi.cover, 'rb') as f:
                    cdata = f.read()
            elif mi.cover_data[1] is not None:
                cdata = mi.cover_data[1]
            if cdata is None:
                return error_dialog(self.gui, _('Could not read cover'),
                            _('Could not read cover from %s format')%fmt.upper(), show=True)
        db.set_cover({book_id:cdata})
        current_idx = self.gui.library_view.currentIndex()
        self.gui.library_view.model().current_changed(current_idx, current_idx)
        self.gui.refresh_cover_browser()
