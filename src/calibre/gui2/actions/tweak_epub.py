#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import iswindows, isosx
from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.tweak_epub import TweakEpub

class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Tweak ePub'), 'tweak_epub.png', 'Edit ePub in situ',
                   _('T'))
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self._edit_epub_in_situ)

    def _edit_epub_in_situ(self, *args):

        # Assure exactly one row selected
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot tweak ePub'), _('No book selected'))
            d.exec_()
            return
        if len(rows) > 1:
            d = error_dialog(self.gui, _('Cannot tweak ePub'), _('Multiple books selected'))
            d.exec_()
            return

        # Confirm 'EPUB' in formats
        row = rows[0].row()
        formats = self.gui.library_view.model().db.formats(row).upper().split(',')
        if not 'EPUB' in formats:
            d = error_dialog(self.gui, _('Cannot tweak ePub'), _('No EPUB available'))
            d.exec_()
            return

        path_to_epub = self.gui.library_view.model().db.format_abspath(row, 'EPUB')
        id = self._get_selected_id()

        # Launch a modal dialog waiting for user to complete or cancel
        dlg = TweakEpub(self.gui, path_to_epub)
        if dlg.exec_() == dlg.Accepted:
            self._update_db(id, dlg._output)
        dlg.cleanup()

    def _get_selected_id(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        return map(self.gui.library_view.model().id, rows)[0]

    def _update_db(self, id, rebuilt):
        '''
        Update the calibre db with the tweaked epub
        '''
        print "gui2.actions.tweak_epub:TweakEpubAction._update_db()"
        print " updating id %d from %s" % (id, rebuilt)
        self.gui.library_view.model().db.add_format_with_hooks(id, 'EPUB', rebuilt, index_is_id=True)

