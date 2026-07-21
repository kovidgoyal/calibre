#!/usr/bin/env python

__license__ = 'GPL v3'
__copyright__ = '2024'
__docformat__ = 'restructuredtext en'

import os
import shutil

from calibre.gui2.dialogs.progress import ProgressDialog
from qt.core import QDialog

from calibre.constants import ismacos
from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceActionWithLibraryDrop
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.utils.localization import _
from calibre.ptempfile import PersistentTemporaryDirectory


class AirdropAction(InterfaceActionWithLibraryDrop):

    name = 'AirDrop books'
    action_spec = (_('AirDrop books'), 'send.png',
                   _('Share the selected books via AirDrop'), ())
    action_type = 'current'
    dont_add_to = frozenset(('context-menu-device',))

    def genesis(self):
        self.qaction.triggered.connect(self.airdrop_books)

    def do_drop(self):
        book_ids = self.dropped_ids
        del self.dropped_ids
        if book_ids:
            self.airdrop_book_ids(book_ids)

    def location_selected(self, loc):
        self.qaction.setEnabled(loc == 'library')

    def airdrop_books(self):
        book_ids = self.gui.library_view.get_selected_ids()
        if not book_ids:
            return error_dialog(self.gui, _('Cannot AirDrop'),
                    _('No book selected'), show=True)
        self.airdrop_book_ids(book_ids)

    def airdrop_book_ids(self, book_ids):
        if not ismacos:
            return error_dialog(self.gui, _('Cannot AirDrop'),
                    _('AirDrop is only available on macOS'), show=True)
        db = self.gui.current_db.new_api
        formats = {book_id: [f.upper() for f in db.formats(book_id)] for book_id in book_ids}
        all_fmts = sorted({f for fmts in formats.values() for f in fmts})
        if not all_fmts:
            return error_dialog(self.gui, _('Cannot AirDrop'),
                    _('The selected books have no files to share'), show=True)
        if len(all_fmts) > 1:
            d = ChooseFormatDialog(self.gui, _('Choose the format to AirDrop'), all_fmts)
            if d.exec() != QDialog.DialogCode.Accepted or not d.format():
                return
            fmt = d.format()
        else:
            fmt = all_fmts[0]
        lib_paths = []
        skipped = 0
        for book_id in book_ids:
            path = db.format_abspath(book_id, fmt) if fmt in formats[book_id] else None
            if path:
                lib_paths.append(path)
            else:
                skipped += 1

        if not lib_paths:
            return error_dialog(self.gui, _('Cannot AirDrop'),
                    _('The selected books are not available in the %s format') % fmt, show=True)
        
        temp_dir = PersistentTemporaryDirectory()
        pd = ProgressDialog(_('Exporting books for AirDrop...'), min=0, max=0, icon='send.png')

        paths = []

        for path in lib_paths:
            pd.set_msg(_('Exporting %s') % path)
            pd.set_value(0)
            if os.access(path, os.R_OK):
                dest = os.path.abspath(os.path.join(temp_dir, os.path.relpath(path, os.path.dirname(path))))
                try:
                    shutil.copy2(path, dest)
                except FileNotFoundError:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(path, dest)

                paths.append(dest)

        try:
            from calibre_extensions.cocoa import airdrop_share
            airdrop_share(*paths)
        except Exception as err:
            import traceback
            return error_dialog(self.gui, _('AirDrop failed'), str(err),
                    det_msg=traceback.format_exc(), show=True)
        if skipped:
            info_dialog(self.gui, _('Some books skipped'),
                    _('%(num)d of the selected books were not available in the'
                      ' %(fmt)s format and were not sent.') % dict(num=skipped, fmt=fmt),
                    show=True)
