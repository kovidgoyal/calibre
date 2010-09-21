#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.tweak_epub import TweakEpub

class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Tweak ePub'), 'trim.png',
            _('Make small changes to ePub format books'),
            _('T'))
    dont_add_to = frozenset(['toolbar-device', 'context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.edit_epub_in_situ)

    def edit_epub_in_situ(self, *args):
        row = self.gui.library_view.currentIndex()
        if not row.isValid():
            return error_dialog(self.gui, _('Cannot tweak ePub'),
                    _('No book selected'), show=True)

        # Confirm 'EPUB' in formats
        book_id = self.gui.library_view.model().id(row)
        try:
            path_to_epub = self.gui.library_view.model().db.format_abspath(
                    book_id, 'EPUB', index_is_id=True)
        except:
            path_to_epub = None

        if not path_to_epub:
            return error_dialog(self.gui, _('Cannot tweak ePub'),
                    _('No ePub available. First convert the book to ePub.'),
                    show=True)

        # Launch modal dialog waiting for user to tweak or cancel
        dlg = TweakEpub(self.gui, path_to_epub)
        if dlg.exec_() == dlg.Accepted:
            self.update_db(book_id, dlg._output)
        dlg.cleanup()

    def update_db(self, book_id, rebuilt):
        '''
        Update the calibre db with the tweaked epub
        '''
        self.gui.library_view.model().db.add_format(book_id, 'EPUB',
                open(rebuilt, 'rb'), index_is_id=True)

