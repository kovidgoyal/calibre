#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import errno
from functools import partial
from collections import Counter

from PyQt5.Qt import QObject, QTimer, QModelIndex

from calibre.constants import isosx
from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.dialogs.delete_matching_from_device import DeleteMatchingFromDeviceDialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.confirm_delete_location import confirm_location
from calibre.gui2.actions import InterfaceAction
from calibre.utils.recycle_bin import can_recycle

single_shot = partial(QTimer.singleShot, 10)


class MultiDeleter(QObject):  # {{{

    def __init__(self, gui, ids, callback):
        from calibre.gui2.dialogs.progress import ProgressDialog
        QObject.__init__(self, gui)
        self.model = gui.library_view.model()
        self.ids = ids
        self.permanent = False
        if can_recycle and len(ids) > 100:
            if question_dialog(gui, _('Are you sure?'), '<p>'+
                _('You are trying to delete %d books. '
                    'Sending so many files to the Recycle'
                    ' Bin <b>can be slow</b>. Should calibre skip the'
                    ' Recycle Bin? If you click Yes the files'
                    ' will be <b>permanently deleted</b>.')%len(ids)):
                self.permanent = True
        self.gui = gui
        self.failures = []
        self.deleted_ids = []
        self.callback = callback
        single_shot(self.delete_one)
        self.pd = ProgressDialog(_('Deleting...'), parent=gui,
                cancelable=False, min=0, max=len(self.ids), icon='trash.png')
        self.pd.setModal(True)
        self.pd.show()

    def delete_one(self):
        if not self.ids:
            self.cleanup()
            return
        id_ = self.ids.pop()
        title = 'id:%d'%id_
        try:
            title_ = self.model.db.title(id_, index_is_id=True)
            if title_:
                title = title_
            self.model.db.delete_book(id_, notify=False, commit=False,
                    permanent=self.permanent)
            self.deleted_ids.append(id_)
        except:
            import traceback
            self.failures.append((id_, title, traceback.format_exc()))
        single_shot(self.delete_one)
        self.pd.value += 1
        self.pd.set_msg(_('Deleted') + ' ' + title)

    def cleanup(self):
        self.pd.hide()
        self.pd = None
        self.model.db.commit()
        self.model.db.clean()
        self.model.books_deleted()
        self.gui.tags_view.recount()
        self.callback(self.deleted_ids)
        if self.failures:
            msg = ['==> '+x[1]+'\n'+x[2] for x in self.failures]
            error_dialog(self.gui, _('Failed to delete'),
                    _('Failed to delete some books, click the "Show details" button'
                    ' for details.'), det_msg='\n\n'.join(msg), show=True)
# }}}


class DeleteAction(InterfaceAction):

    name = 'Remove Books'
    action_spec = (_('Remove books'), 'remove_books.png', _('Delete books'), 'Backspace' if isosx else 'Del')
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Remove selected books')

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
            self.do_library_delete(book_ids)

    def genesis(self):
        self.qaction.triggered.connect(self.delete_books)
        self.delete_menu = self.qaction.menu()
        m = partial(self.create_menu_action, self.delete_menu)
        m('delete-specific',
                _('Remove files of a specific format from selected books...'),
                triggered=self.delete_selected_formats)
        m('delete-except',
                _('Remove all formats from selected books, except...'),
                triggered=self.delete_all_but_selected_formats)
        m('delete-all',
                _('Remove all formats from selected books'),
                triggered=self.delete_all_formats)
        m('delete-covers',
                _('Remove covers from selected books'),
                triggered=self.delete_covers)
        self.delete_menu.addSeparator()
        m('delete-matching',
                _('Remove matching books from device'),
                triggered=self.remove_matching_books_from_device)
        self.qaction.setMenu(self.delete_menu)
        self.delete_memory = {}

    def location_selected(self, loc):
        enabled = loc == 'library'
        for action in list(self.delete_menu.actions())[1:]:
            action.setEnabled(enabled)

    def _get_selected_formats(self, msg, ids, exclude=False, single=False):
        from calibre.gui2.dialogs.select_formats import SelectFormats
        c = Counter()
        db = self.gui.library_view.model().db
        for x in ids:
            fmts_ = db.formats(x, index_is_id=True, verify_formats=False)
            if fmts_:
                for x in frozenset([x.lower() for x in fmts_.split(',')]):
                    c[x] += 1
        d = SelectFormats(c, msg, parent=self.gui, exclude=exclude,
                single=single)
        if d.exec_() != d.Accepted:
            return None
        return d.selected_formats

    def _get_selected_ids(self, err_title=_('Cannot delete')):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, err_title, _('No book selected'))
            d.exec_()
            return set([])
        return set(map(self.gui.library_view.model().id, rows))

    def remove_format_by_id(self, book_id, fmt):
        title = self.gui.current_db.title(book_id, index_is_id=True)
        if not confirm('<p>'+(_(
            'The %(fmt)s format will be <b>permanently deleted</b> from '
            '%(title)s. Are you sure?')%dict(fmt=fmt, title=title)) +
                       '</p>', 'library_delete_specific_format', self.gui):
            return

        self.gui.library_view.model().db.remove_format(book_id, fmt,
                index_is_id=True, notify=False)
        self.gui.library_view.model().refresh_ids([book_id])
        self.gui.library_view.model().current_changed(self.gui.library_view.currentIndex(),
                self.gui.library_view.currentIndex())
        self.gui.tags_view.recount()

    def restore_format(self, book_id, original_fmt):
        self.gui.current_db.restore_original_format(book_id, original_fmt)
        self.gui.library_view.model().refresh_ids([book_id])
        self.gui.library_view.model().current_changed(self.gui.library_view.currentIndex(),
                self.gui.library_view.currentIndex())
        self.gui.tags_view.recount()

    def delete_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            _('Choose formats to be deleted'), ids)
        if not fmts:
            return
        m = self.gui.library_view.model()
        m.db.new_api.remove_formats({book_id:fmts for book_id in ids})
        m.refresh_ids(ids)
        m.current_changed(self.gui.library_view.currentIndex(),
                self.gui.library_view.currentIndex())
        if ids:
            self.gui.tags_view.recount()

    def delete_all_but_selected_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        fmts = self._get_selected_formats(
            '<p>'+_('Choose formats <b>not</b> to be deleted.<p>Note that '
                'this will never remove all formats from a book.'), ids,
            exclude=True)
        if fmts is None:
            return
        m = self.gui.library_view.model()
        removals = {}
        for id in ids:
            bfmts = m.db.formats(id, index_is_id=True)
            if bfmts is None:
                continue
            bfmts = set([x.lower() for x in bfmts.split(',')])
            rfmts = bfmts - set(fmts)
            if bfmts - rfmts:
                # Do not delete if it will leave the book with no
                # formats
                removals[id] = rfmts
        if removals:
            m.db.new_api.remove_formats(removals)
            m.refresh_ids(ids)
            m.current_changed(self.gui.library_view.currentIndex(),
                    self.gui.library_view.currentIndex())
            if ids:
                self.gui.tags_view.recount()

    def delete_all_formats(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        if not confirm('<p>'+_('<b>All formats</b> for the selected books will '
                               'be <b>deleted</b> from your library.<br>'
                               'The book metadata will be kept. Are you sure?') +
                       '</p>', 'delete_all_formats', self.gui):
            return
        db = self.gui.library_view.model().db
        removals = {}
        for id in ids:
            fmts = db.formats(id, index_is_id=True, verify_formats=False)
            if fmts:
                removals[id] = fmts.split(',')
        if removals:
            db.new_api.remove_formats(removals)
            self.gui.library_view.model().refresh_ids(ids)
            self.gui.library_view.model().current_changed(self.gui.library_view.currentIndex(),
                    self.gui.library_view.currentIndex())
            if ids:
                self.gui.tags_view.recount()

    def remove_matching_books_from_device(self, *args):
        if not self.gui.device_manager.is_device_present:
            d = error_dialog(self.gui, _('Cannot delete books'),
                             _('No device is connected'))
            d.exec_()
            return
        ids = self._get_selected_ids()
        if not ids:
            # _get_selected_ids shows a dialog box if nothing is selected, so we
            # do not need to show one here
            return
        to_delete = {}
        some_to_delete = False
        for model,name in ((self.gui.memory_view.model(), _('Main memory')),
                           (self.gui.card_a_view.model(), _('Storage Card A')),
                           (self.gui.card_b_view.model(), _('Storage Card B'))):
            to_delete[name] = (model, model.paths_for_db_ids(ids))
            if len(to_delete[name][1]) > 0:
                some_to_delete = True
        if not some_to_delete:
            d = error_dialog(self.gui, _('No books to delete'),
                             _('None of the selected books are on the device'))
            d.exec_()
            return
        d = DeleteMatchingFromDeviceDialog(self.gui, to_delete)
        if d.exec_():
            paths = {}
            ids = {}
            for (model, id, path) in d.result:
                if model not in paths:
                    paths[model] = []
                    ids[model] = []
                paths[model].append(path)
                ids[model].append(id)
            cv, row = self.gui.current_view(), -1
            if cv is not self.gui.library_view:
                row = cv.currentIndex().row()
            for model in paths:
                job = self.gui.remove_paths(paths[model])
                self.delete_memory[job] = (paths[model], model)

                model.mark_for_deletion(job, ids[model], rows_are_ids=True)
            self.gui.status_bar.show_message(_('Deleting books from device.'), 1000)
            if row > -1:
                nrow = row - 1 if row > 0 else row + 1
                cv.set_current_row(min(cv.model().rowCount(None), max(0, nrow)))

    def delete_covers(self, *args):
        ids = self._get_selected_ids()
        if not ids:
            return
        for id in ids:
            self.gui.library_view.model().db.remove_cover(id)
        self.gui.library_view.model().refresh_ids(ids)
        self.gui.library_view.model().current_changed(self.gui.library_view.currentIndex(),
                self.gui.library_view.currentIndex())

    def library_ids_deleted(self, ids_deleted, current_row=None):
        view = self.gui.library_view
        for v in (self.gui.memory_view, self.gui.card_a_view, self.gui.card_b_view):
            if v is None:
                continue
            v.model().clear_ondevice(ids_deleted)
        if current_row is not None:
            ci = view.model().index(current_row, 0)
            if not ci.isValid():
                # Current row is after the last row, set it to the last row
                current_row = view.row_count() - 1
            view.set_current_row(current_row)
        if view.model().rowCount(QModelIndex()) < 1:
            self.gui.book_details.reset_info()

    def library_ids_deleted2(self, ids_deleted, next_id=None):
        view = self.gui.library_view
        current_row = None
        if next_id is not None:
            rmap = view.ids_to_rows([next_id])
            current_row = rmap.get(next_id, None)
        self.library_ids_deleted(ids_deleted, current_row=current_row)

    def do_library_delete(self, to_delete_ids):
        view = self.gui.current_view()
        next_id = view.next_id
        # Ask the user if they want to delete the book from the library or device if it is in both.
        if self.gui.device_manager.is_device_present:
            on_device = False
            on_device_ids = self._get_selected_ids()
            for id in on_device_ids:
                res = self.gui.book_on_device(id)
                if res[0] or res[1] or res[2]:
                    on_device = True
                if on_device:
                    break
            if on_device:
                loc = confirm_location('<p>' + _('Some of the selected books are on the attached device. '
                                            '<b>Where</b> do you want the selected files deleted from?'),
                            self.gui)
                if not loc:
                    return
                elif loc == 'dev':
                    self.remove_matching_books_from_device()
                    return
                elif loc == 'both':
                    self.remove_matching_books_from_device()
        # The following will run if the selected books are not on a connected device.
        # The user has selected to delete from the library or the device and library.
        if not confirm('<p>'+ngettext(
                'The selected book will be <b>permanently deleted</b> and the files '
                'removed from your calibre library. Are you sure?',
                'The {} selected books will be <b>permanently deleted</b> and the files '
                'removed from your calibre library. Are you sure?', len(to_delete_ids)).format(len(to_delete_ids)),
                'library_delete_books', self.gui):
            return
        if len(to_delete_ids) < 5:
            try:
                view.model().delete_books_by_id(to_delete_ids)
            except IOError as err:
                if err.errno == errno.EACCES:
                    import traceback
                    fname = getattr(err, 'filename', 'file') or 'file'
                    return error_dialog(self.gui, _('Permission denied'),
                            _('Could not access %s. Is it being used by another'
                            ' program? Click "Show details" for more information.')%fname, det_msg=traceback.format_exc(),
                            show=True)

            self.library_ids_deleted2(to_delete_ids, next_id=next_id)
        else:
            self.__md = MultiDeleter(self.gui, to_delete_ids,
                    partial(self.library_ids_deleted2, next_id=next_id))

    def delete_books(self, *args):
        '''
        Delete selected books from device or library.
        '''
        view = self.gui.current_view()
        rows = view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        # Library view is visible.
        if self.gui.stack.currentIndex() == 0:
            to_delete_ids = [view.model().id(r) for r in rows]
            self.do_library_delete(to_delete_ids)
        # Device view is visible.
        else:
            cv, row = self.gui.current_view(), -1
            if cv is not self.gui.library_view:
                row = cv.currentIndex().row()
            if self.gui.stack.currentIndex() == 1:
                view = self.gui.memory_view
            elif self.gui.stack.currentIndex() == 2:
                view = self.gui.card_a_view
            else:
                view = self.gui.card_b_view
            paths = view.model().paths(rows)
            ids = view.model().indices(rows)
            if not confirm('<p>'+ngettext(
                    'The selected book will be <b>permanently deleted</b> from your device. Are you sure?',
                    'The {} selected books will be <b>permanently deleted</b> from your device. Are you sure?', len(paths)).format(len(paths)),
                    'device_delete_books', self.gui):
                return
            job = self.gui.remove_paths(paths)
            self.delete_memory[job] = (paths, view.model())
            view.model().mark_for_deletion(job, ids, rows_are_ids=True)
            self.gui.status_bar.show_message(_('Deleting books from device.'), 1000)
            if row > -1:
                nrow = row - 1 if row > 0 else row + 1
                cv.set_current_row(min(cv.model().rowCount(None), max(0, nrow)))
