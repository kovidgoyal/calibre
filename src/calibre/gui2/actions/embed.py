#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import QTimer, QProgressDialog, Qt

from calibre.gui2 import warning_dialog
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
            self.dropped_ids = tuple(map(int, str(mime_data.data(mime)).split()))
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
                _('Embed metadata into files of a specific format from selected books..'),
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
            if errors:
                det_msg = [_('The {0} format of {1}:\n{2}').format((fmt or '').upper(), mi.title, tb) for mi, fmt, tb in errors]
                warning_dialog(
                    self.gui, _('Failed for some files'), _(
                    'Failed to embed metadata into some book files. Click "Show details" for details.'),
                    det_msg='\n\n'.join(det_msg), show=True)
            return
        pd.setValue(i)
        db = self.gui.current_db.new_api
        def report_error(mi, fmt, tb):
            errors.append((mi, fmt, tb))
        db.embed_metadata((book_ids[i],), only_fmts=only_fmts, report_error=report_error)
        self.job_data = (i + 1, book_ids, pd, only_fmts, errors)

