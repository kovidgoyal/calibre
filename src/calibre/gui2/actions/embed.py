#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt5.Qt import QTimer, QProgressDialog, Qt

from calibre import force_unicode
from calibre.gui2 import gprefs
from calibre.gui2.actions import InterfaceAction


class EmbedAction(InterfaceAction):

    name = 'Embed Metadata'
    action_spec = (_('Embed metadata'), 'modified.png', _('Embed metadata into book files'), None)
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Embed metadata into book files')

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
            self.dropped_ids = tuple(map(int, mime_data.data(mime).data().split()))
            QTimer.singleShot(1, self.do_drop)
            return True
        return False

    def do_drop(self):
        book_ids = self.dropped_ids
        del self.dropped_ids
        if book_ids:
            self.do_embed(book_ids)

    def genesis(self):
        self.qaction.triggered.connect(self.embed)
        self.embed_menu = self.qaction.menu()
        m = partial(self.create_menu_action, self.embed_menu)
        m('embed-specific',
                _('Embed metadata into files of a specific format from selected books...'),
                triggered=self.embed_selected_formats)
        self.qaction.setMenu(self.embed_menu)
        self.pd_timer = t = QTimer()
        t.timeout.connect(self.do_one)

    def embed(self):
        rb = self.gui.iactions['Remove Books']
        ids = rb._get_selected_ids(err_title=_('Cannot embed'))
        if not ids:
            return
        self.do_embed(ids)

    def embed_selected_formats(self):
        rb = self.gui.iactions['Remove Books']
        ids = rb._get_selected_ids(err_title=_('Cannot embed'))
        if not ids:
            return
        fmts = rb._get_selected_formats(
            _('Choose formats to be updated'), ids)
        if not fmts:
            return
        self.do_embed(ids, fmts)

    def do_embed(self, book_ids, only_fmts=None):
        pd = QProgressDialog(_('Embedding updated metadata into book files...'), _('&Stop'), 0, len(book_ids), self.gui)
        pd.setWindowTitle(_('Embedding metadata...'))
        pd.setWindowModality(Qt.WindowModal)
        errors = []
        self.job_data = (0, tuple(book_ids), pd, only_fmts, errors)
        self.pd_timer.start()

    def do_one(self):
        try:
            i, book_ids, pd, only_fmts, errors = self.job_data
        except (TypeError, AttributeError):
            return
        if i >= len(book_ids) or pd.wasCanceled():
            pd.setValue(pd.maximum())
            pd.hide()
            self.pd_timer.stop()
            self.job_data = None
            self.gui.library_view.model().refresh_ids(book_ids)
            if i > 0:
                self.gui.status_bar.show_message(ngettext(
                    'Embedded metadata in one book', 'Embedded metadata in {} books', i).format(i), 5000)
            if errors:
                det_msg = '\n\n'.join([_('The {0} format of {1}:\n\n{2}\n').format(
                    (fmt or '').upper(), force_unicode(mi.title), force_unicode(tb)) for mi, fmt, tb in errors])
                from calibre.gui2.dialogs.message_box import MessageBox
                title, msg = _('Failed for some files'), _(
                    'Failed to embed metadata into some book files. Click "Show details" for details.')
                d = MessageBox(MessageBox.WARNING, _('WARNING:')+ ' ' + title, msg, det_msg, parent=self.gui, show_copy_button=True)
                tc = d.toggle_checkbox
                tc.setVisible(True), tc.setText(_('Show the &failed books in the main book list'))
                tc.setChecked(gprefs.get('show-embed-failed-books', False))
                d.resize_needed.emit()
                d.exec_()
                gprefs['show-embed-failed-books'] = tc.isChecked()
                if tc.isChecked():
                    failed_ids = {mi.book_id for mi, fmt, tb in errors}
                    db = self.gui.current_db
                    db.data.set_marked_ids(failed_ids)
                    self.gui.search.set_search_string('marked:true')
            return
        pd.setValue(i)
        db = self.gui.current_db.new_api
        book_id = book_ids[i]

        def report_error(mi, fmt, tb):
            mi.book_id = book_id
            errors.append((mi, fmt, tb))
        db.embed_metadata((book_id,), only_fmts=only_fmts, report_error=report_error)
        self.job_data = (i + 1, book_ids, pd, only_fmts, errors)
