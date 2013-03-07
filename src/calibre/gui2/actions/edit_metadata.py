#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil
from functools import partial

from PyQt4.Qt import QMenu, QModelIndex, QTimer

from calibre.gui2 import error_dialog, Dispatcher, question_dialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.device_category_editor import DeviceCategoryEditor
from calibre.gui2.actions import InterfaceAction
from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.opf2 import OPF
from calibre.utils.icu import sort_key
from calibre.db.errors import NoSuchFormat

class EditMetadataAction(InterfaceAction):

    name = 'Edit Metadata'
    action_spec = (_('Edit metadata'), 'edit_input.png', _('Change the title/author/cover etc. of books'), _('E'))
    action_type = 'current'
    action_add_menu = True

    accepts_drops = True

    def accept_enter_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def accept_drag_move_event(self, event, mime_data):
        if mime_data.hasFormat("application/calibre+from_library"):
            return True
        return False

    def drop_event(self, event, mime_data):
        mime = 'application/calibre+from_library'
        if mime_data.hasFormat(mime):
            self.dropped_ids = tuple(map(int, str(mime_data.data(mime)).split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

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
        md.addSeparator()
        cm('bulk', _('Edit metadata in bulk'),
                triggered=partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        cm('download', _('Download metadata and covers'),
                triggered=partial(self.download_metadata, ids=None),
                shortcut='Ctrl+D')
        self.metadata_menu = md

        mb = QMenu()
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
        self.action_merge = cm('merge', _('Merge book records'), icon='merge_books.png',
            shortcut=_('M'), triggered=self.merge_books)
        self.action_merge.setMenu(mb)

        self.qaction.triggered.connect(self.edit_metadata)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.action_merge.setEnabled(enabled)

    # Download metadata {{{
    def download_metadata(self, ids=None, ensure_fields=None):
        if ids is None:
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) == 0:
                return error_dialog(self.gui, _('Cannot download metadata'),
                            _('No books selected'), show=True)
            db = self.gui.library_view.model().db
            ids = [db.id(row.row()) for row in rows]
        from calibre.gui2.metadata.bulk_download import start_download
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
            return error_dialog(self.gui, _('Download failed'),
            _('Failed to download metadata or covers for any of the %d'
               ' book(s).') % num, det_msg=det_msg, show=True)

        self.gui.status_bar.show_message(_('Metadata download completed'), 3000)

        msg = '<p>' + _('Finished downloading metadata for <b>%d book(s)</b>. '
            'Proceed with updating the metadata in your library?')%len(id_map)

        show_copy_button = False
        checkbox_msg = None
        if failed_ids or failed_covers:
            show_copy_button = True
            num = len(failed_ids.union(failed_covers))
            msg += '<p>'+_('Could not download metadata and/or covers for %d of the books. Click'
                    ' "Show details" to see which books.')%num
            checkbox_msg = _('Show the &failed books in the main book list '
                    'after updating metadata')

        payload = (id_map, tdir, log_file, lm_map,
                failed_ids.union(failed_covers))
        self.gui.proceed_question(self.apply_downloaded_metadata, payload,
                log_file, _('Download log'), _('Download complete'), msg,
                det_msg=det_msg, show_copy_button=show_copy_button,
                cancel_callback=partial(self.cleanup_bulk_download, tdir),
                log_is_file=True, checkbox_msg=checkbox_msg,
                checkbox_checked=False)

    def apply_downloaded_metadata(self, payload, *args):
        good_ids, tdir, log_file, lm_map, failed_ids = payload
        if not good_ids:
            return

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
            if not question_dialog(self.gui, _('Some books changed'), '<p>'+
                    _('The metadata for some books in your library has'
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

        restrict_to_failed = bool(args and args[0])
        if restrict_to_failed:
            db.data.set_marked_ids(failed_ids)

        self.apply_metadata_changes(id_map,
                callback=partial(self.downloaded_metadata_applied, tdir,
                    restrict_to_failed))

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
            d.exec_()
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

        if len(row_list) == 1:
            cr = row_list[0]
            row_list = \
                list(range(self.gui.library_view.model().rowCount(QModelIndex())))
            current_row = row_list.index(cr)

        changed, rows_to_refresh = self.do_edit_metadata(row_list, current_row)

        m = self.gui.library_view.model()

        if rows_to_refresh:
            m.refresh_rows(rows_to_refresh)

        if changed:
            m.refresh_ids(list(changed))
            current = self.gui.library_view.currentIndex()
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
            m.current_changed(current, previous)
            self.gui.tags_view.recount()

    def do_edit_metadata(self, row_list, current_row):
        from calibre.gui2.metadata.single import edit_metadata
        db = self.gui.library_view.model().db
        changed, rows_to_refresh = edit_metadata(db, row_list, current_row,
                parent=self.gui, view_slot=self.view_format_callback,
                set_current_callback=self.set_current_callback)
        return changed, rows_to_refresh

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
            db = self.gui.library_view.model().db
            view.view_format(db.row(id_), fmt)

    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in \
                self.gui.library_view.selectionModel().selectedRows()]
        m = self.gui.library_view.model()
        ids = [m.id(r) for r in rows]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit metadata'),
                    _('No books selected'))
            d.exec_()
            return
        self.do_edit_bulk_metadata(rows, ids)

    def do_edit_bulk_metadata(self, rows, book_ids):
        # Prevent the TagView from updating due to signals from the database
        self.gui.tags_view.blockSignals(True)
        changed = False
        try:
            current_tab = 0
            while True:
                dialog = MetadataBulkDialog(self.gui, rows,
                                self.gui.library_view.model(), current_tab)
                if dialog.changed:
                    changed = True
                if not dialog.do_again:
                    break
                current_tab = dialog.central_widget.currentIndex()
        finally:
            self.gui.tags_view.blockSignals(False)
        if changed:
            m = self.gui.library_view.model()
            m.refresh(reset=False)
            m.research()
            self.gui.tags_view.recount()
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
            self.gui.library_view.select_rows(book_ids)

    # Merge books {{{
    def merge_books(self, safe_merge=False, merge_only_formats=False):
        '''
        Merge selected books in library.
        '''
        if self.gui.stack.currentIndex() != 0:
            return
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot merge books'),
                                _('No books selected'), show=True)
        if len(rows) < 2:
            return error_dialog(self.gui, _('Cannot merge books'),
                        _('At least two books must be selected for merging'),
                        show=True)
        if len(rows) > 5:
            if not confirm('<p>'+_('You are about to merge more than 5 books.  '
                                    'Are you <b>sure</b> you want to proceed?')
                                +'</p>', 'merge_too_many_books', self.gui):
                return

        dest_id, src_ids = self.books_to_merge(rows)
        title = self.gui.library_view.model().db.title(dest_id, index_is_id=True)
        if safe_merge:
            if not confirm('<p>'+_(
                'Book formats and metadata from the selected books '
                'will be added to the <b>first selected book</b> (%s). '
                'ISBN will <i>not</i> be merged.<br><br> '
                'The second and subsequently selected books will not '
                'be deleted or changed.<br><br>'
                'Please confirm you want to proceed.')%title
            +'</p>', 'merge_books_safe', self.gui):
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.merge_metadata(dest_id, src_ids)
        elif merge_only_formats:
            if not confirm('<p>'+_(
                'Book formats from the selected books will be merged '
                'into the <b>first selected book</b> (%s). '
                'Metadata in the first selected book will not be changed. '
                'Author, Title, ISBN and all other metadata will <i>not</i> be merged.<br><br>'
                'After merger the second and subsequently '
                'selected books, with any metadata they have will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title
            +'</p>', 'merge_only_formats', self.gui):
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.delete_books_after_merge(src_ids)
        else:
            if not confirm('<p>'+_(
                'Book formats and metadata from the selected books will be merged '
                'into the <b>first selected book</b> (%s). '
                'ISBN will <i>not</i> be merged.<br><br>'
                'After merger the second and '
                'subsequently selected books will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title
            +'</p>', 'merge_books', self.gui):
                return
            self.add_formats(dest_id, self.formats_for_books(rows))
            self.merge_metadata(dest_id, src_ids)
            self.delete_books_after_merge(src_ids)
            # leave the selection highlight on first selected book
            dest_row = rows[0].row()
            for row in rows:
                if row.row() < rows[0].row():
                    dest_row -= 1
            ci = self.gui.library_view.model().index(dest_row, 0)
            if ci.isValid():
                self.gui.library_view.setCurrentIndex(ci)
                self.gui.library_view.model().current_changed(ci, ci)

    def add_formats(self, dest_id, src_books, replace=False):
        for src_book in src_books:
            if src_book:
                fmt = os.path.splitext(src_book)[-1].replace('.', '').upper()
                with open(src_book, 'rb') as f:
                    self.gui.library_view.model().db.add_format(dest_id, fmt, f, index_is_id=True,
                            notify=False, replace=replace)

    def formats_for_books(self, rows):
        m = self.gui.library_view.model()
        ans = []
        for id_ in map(m.id, rows):
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

    def merge_metadata(self, dest_id, src_ids):
        db = self.gui.library_view.model().db
        dest_mi = db.get_metadata(dest_id, index_is_id=True)
        orig_dest_comments = dest_mi.comments
        dest_cover = db.cover(dest_id, index_is_id=True)
        had_orig_cover = bool(dest_cover)
        for src_id in src_ids:
            src_mi = db.get_metadata(src_id, index_is_id=True)
            if src_mi.comments and orig_dest_comments != src_mi.comments:
                if not dest_mi.comments:
                    dest_mi.comments = src_mi.comments
                else:
                    dest_mi.comments = unicode(dest_mi.comments) + u'\n\n' + unicode(src_mi.comments)
            if src_mi.title and (not dest_mi.title or
                    dest_mi.title == _('Unknown')):
                dest_mi.title = src_mi.title
            if src_mi.title and (not dest_mi.authors or dest_mi.authors[0] ==
                    _('Unknown')):
                dest_mi.authors = src_mi.authors
                dest_mi.author_sort = src_mi.author_sort
            if src_mi.tags:
                if not dest_mi.tags:
                    dest_mi.tags = src_mi.tags
                else:
                    dest_mi.tags.extend(src_mi.tags)
            if not dest_cover:
                src_cover = db.cover(src_id, index_is_id=True)
                if src_cover:
                    dest_cover = src_cover
            if not dest_mi.publisher:
                dest_mi.publisher = src_mi.publisher
            if not dest_mi.rating:
                dest_mi.rating = src_mi.rating
            if not dest_mi.series:
                dest_mi.series = src_mi.series
                dest_mi.series_index = src_mi.series_index
        db.set_metadata(dest_id, dest_mi, ignore_errors=False)
        if not had_orig_cover and dest_cover:
            db.set_cover(dest_id, dest_cover)

        for key in db.field_metadata: #loop thru all defined fields
          if db.field_metadata[key]['is_custom']:
            colnum = db.field_metadata[key]['colnum']
            # Get orig_dest_comments before it gets changed
            if db.field_metadata[key]['datatype'] == 'comments':
              orig_dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)
            for src_id in src_ids:
              dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)
              src_value = db.get_custom(src_id, num=colnum, index_is_id=True)
              if db.field_metadata[key]['datatype'] == 'comments':
                if src_value and src_value != orig_dest_value:
                  if not dest_value:
                    db.set_custom(dest_id, src_value, num=colnum)
                  else:
                    dest_value = unicode(dest_value) + u'\n\n' + unicode(src_value)
                    db.set_custom(dest_id, dest_value, num=colnum)
              if db.field_metadata[key]['datatype'] in \
                ('bool', 'int', 'float', 'rating', 'datetime') \
                and dest_value is None:
                db.set_custom(dest_id, src_value, num=colnum)
              if db.field_metadata[key]['datatype'] == 'series' \
                and not dest_value:
                if src_value:
                  src_index = db.get_custom_extra(src_id, num=colnum, index_is_id=True)
                  db.set_custom(dest_id, src_value, num=colnum, extra=src_index)
              if (db.field_metadata[key]['datatype'] == 'enumeration' or
                        (db.field_metadata[key]['datatype'] == 'text' and
                         not db.field_metadata[key]['is_multiple'])
                    and not dest_value):
                db.set_custom(dest_id, src_value, num=colnum)
              if db.field_metadata[key]['datatype'] == 'text' \
                and db.field_metadata[key]['is_multiple']:
                if src_value:
                  if not dest_value:
                    dest_value = src_value
                  else:
                    dest_value.extend(src_value)
                  db.set_custom(dest_id, dest_value, num=colnum)
        # }}}

    def edit_device_collections(self, view, oncard=None):
        model = view.model()
        result = model.get_collections_with_ids()
        d = DeviceCategoryEditor(self.gui, tag_to_match=None, data=result, key=sort_key)
        d.exec_()
        if d.result() == d.Accepted:
            to_rename = d.to_rename # dict of new text to old ids
            to_delete = d.to_delete # list of ids
            for old_id, new_name in to_rename.iteritems():
                model.rename_collection(old_id, new_name=unicode(new_name))
            for item in to_delete:
                model.delete_collection_using_id(item)
            self.gui.upload_collections(model.db, view=view, oncard=oncard)
            view.reset()

    # Apply bulk metadata changes {{{
    def apply_metadata_changes(self, id_map, title=None, msg='', callback=None,
            merge_tags=True):
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
        self.apply_id_map = list(id_map.iteritems())
        self.apply_current_idx = 0
        self.apply_failures = []
        self.applied_ids = set()
        self.apply_pd = None
        self.apply_callback = callback
        if len(self.apply_id_map) > 1:
            from calibre.gui2.dialogs.progress import ProgressDialog
            self.apply_pd = ProgressDialog(title, msg, min=0,
                    max=len(self.apply_id_map)-1, parent=self.gui,
                    cancelable=False)
            self.apply_pd.setModal(True)
            self.apply_pd.show()
        self._am_merge_tags = True
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
        QTimer.singleShot(50, self.do_one_apply)


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
                    ' in your library. Click "Show Details" to see '
                    'details.'), det_msg='\n\n'.join(msg), show=True)
        if self.applied_ids:
            cr = self.gui.library_view.currentIndex().row()
            self.gui.library_view.model().refresh_ids(
                list(self.applied_ids), cr)
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
            self.gui.tags_view.recount()

        self.apply_id_map = []
        self.apply_pd = None
        try:
            if callable(self.apply_callback):
                self.apply_callback(list(self.applied_ids))
        finally:
            self.apply_callback = None

    # }}}

