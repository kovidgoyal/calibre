#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.tweak_epub import TweakEpub
from calibre.utils.config import tweaks

class TweakEpubAction(InterfaceAction):

    name = 'Tweak ePub'
    action_spec = (_('Tweak Book'), 'trim.png',
            _('Make small changes to ePub or HTMLZ format books'),
            _('T'))
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.edit_epub_in_situ)

    def edit_epub_in_situ(self, *args):
        row = self.gui.library_view.currentIndex()
        if not row.isValid():
            return error_dialog(self.gui, _('Cannot tweak Book'),
                    _('No book selected'), show=True)

        book_id = self.gui.library_view.model().id(row)

        # Confirm 'EPUB' in formats
        try:
            path_to_epub = self.gui.library_view.model().db.format(
                    book_id, 'EPUB', index_is_id=True, as_path=True)
        except:
            path_to_epub = None

        # Confirm 'HTMLZ' in formats
        try:
            path_to_htmlz = self.gui.library_view.model().db.format(
                    book_id, 'HTMLZ', index_is_id=True, as_path=True)
        except:
            path_to_htmlz = None

        if not path_to_epub and not path_to_htmlz:
            return error_dialog(self.gui, _('Cannot tweak Book'),
                    _('The book must be in ePub or HTMLZ format to tweak.'
                        '\n\nFirst convert the book to ePub or HTMLZ.'),
                    show=True)

        # Launch modal dialog waiting for user to tweak or cancel
        if tweaks['tweak_book_prefer'] == 'htmlz':
            path_to_book = path_to_htmlz or path_to_epub
        else:
            path_to_book = path_to_epub or path_to_htmlz

        dlg = TweakEpub(self.gui, path_to_book)
        if dlg.exec_() == dlg.Accepted:
            self.update_db(book_id, dlg._output)
        dlg.cleanup()
        os.remove(path_to_book)

    def update_db(self, book_id, rebuilt):
        '''
        Update the calibre db with the tweaked epub
        '''
        fmt = os.path.splitext(rebuilt)[1][1:].upper()
        self.gui.library_view.model().db.add_format(book_id, fmt,
                open(rebuilt, 'rb'), index_is_id=True)

