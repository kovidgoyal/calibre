#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os

from qt.core import QDialog

from calibre.constants import ismacos
from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceActionWithLibraryDrop
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.localization import _


class AirdropAction(InterfaceActionWithLibraryDrop):
    name = 'AirDrop books'
    action_spec = (_('AirDrop books'), 'send.png', _('Share the selected books via AirDrop'), ())
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
            return error_dialog(self.gui, _('Cannot AirDrop'), _('No book selected'), show=True)
        self.airdrop_book_ids(book_ids)

    def airdrop_book_ids(self, book_ids):
        if not ismacos:
            return error_dialog(self.gui, _('Cannot AirDrop'), _('AirDrop is only available on macOS'), show=True)
        db = self.gui.current_db.new_api
        formats = {book_id: [f.upper() for f in db.formats(book_id)] for book_id in book_ids}
        all_fmts = {f for fmts in formats.values() for f in fmts}
        if not all_fmts:
            return error_dialog(self.gui, _('Cannot AirDrop'), _('The selected books have no files to share'), show=True)

        def all_have_format(f: str) -> bool:
            for q in formats.values():
                if f not in q:
                    return False
            return True

        common_formats = {f for f in all_fmts if all_have_format(f)}
        if not common_formats:
            return error_dialog(self.gui, _('Cannot AirDrop'), _('The selected books do not all have at least one format in common'), show=True)
        all_fmts = common_formats
        if len(all_fmts) > 1:
            d = ChooseFormatDialog(self.gui, _('Choose the format to AirDrop'), all_fmts)
            if d.exec() != QDialog.DialogCode.Accepted or not d.format():
                return
            fmt = d.format()
        else:
            fmt = tuple(all_fmts)[0]
        temp_dir = PersistentTemporaryDirectory()

        from calibre.gui2.save import Saver

        class Exporter(Saver):
            pd_title = _('Exporting {} books to AirDrop...').format(len(book_ids))

            def on_complete(self):
                paths = tuple(os.path.join(temp_dir, x) for x in os.listdir(temp_dir))
                from calibre_extensions.cocoa import airdrop_share

                try:
                    airdrop_share(*paths)
                except Exception as err:
                    import traceback

                    return error_dialog(self.parent(), _('AirDrop failed'), str(err), det_msg=traceback.format_exc(), show=True)

        self.gui.iactions['Save To Disk'].save_library_format_by_ids(book_ids, fmt, path=temp_dir, saver_class=Exporter)
