#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os
from time import localtime, strftime

from qt.core import QDialogButtonBox, QIcon, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, Qt, QVBoxLayout, QWidget

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _, ngettext

SAVE_NAME_ROLE = Qt.ItemDataRole.UserRole


def fmt_timestamp(ts: float) -> str:
    return strftime('%d %b %Y, %H:%M', localtime(ts))


class ManageSavesDialog(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Manage saved games'), 'cyoa-manage-saves', parent, default_buttons=QDialogButtonBox.StandardButton.Close)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.saves_label = la = QLabel(_('&Saved games:'))
        self.saves_list = sl = QListWidget(self)
        la.setBuddy(sl)
        l.addWidget(la), l.addWidget(sl)
        self.delete_button = b = QPushButton(QIcon.ic('trash.png'), _('&Delete'), self)
        b.setToolTip('<p>' + _('Permanently delete the selected saved game'))
        b.clicked.connect(self.delete_selected)
        self.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        l.addWidget(self.bb)
        self.re_populate()

    def re_populate(self) -> None:
        self.saves_list.clear()
        for e in data.list_games(base=data.saves_dir()):
            turns = ngettext('{} turn', '{} turns', e.num_turns).format(e.num_turns)
            text = f'{e.title} — {turns} — {fmt_timestamp(e.updated)}'
            if e.game_id != e.title:
                text += f' ({e.game_id})'
            i = QListWidgetItem(text, self.saves_list)
            i.setData(SAVE_NAME_ROLE, e.game_id)

    def delete_selected(self) -> None:
        item = self.saves_list.currentItem()
        if item is None:
            return
        name = str(item.data(SAVE_NAME_ROLE))
        if question_dialog(self, _('Are you sure?'), _('Permanently delete the saved game "{}"? This cannot be undone.').format(name)):
            data.delete_game(name, base=data.saves_dir())
            self.re_populate()


class SaveGameDialog(Dialog):
    def __init__(self, default_name: str, parent: QWidget | None = None) -> None:
        self.default_name = default_name
        super().__init__(_('Save game'), 'cyoa-save-game', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.name_label = la = QLabel(_('&Name for this save:'))
        self.name_edit = ne = QLineEdit(self)
        ne.setText(self.default_name)
        ne.setToolTip('<p>' + _('The save is stored in a folder of this name, so characters not allowed in file names are replaced'))
        la.setBuddy(ne)
        l.addWidget(la), l.addWidget(ne)
        self.manage_button = mb = QPushButton(QIcon.ic('config.png'), _('&Manage saves'), self)
        mb.setToolTip('<p>' + _('Browse and delete previously saved games'))
        mb.clicked.connect(self.manage_saves)
        self.bb.addButton(mb, QDialogButtonBox.ButtonRole.ActionRole)
        l.addWidget(self.bb)

    def manage_saves(self) -> None:
        ManageSavesDialog(self).exec()

    @property
    def save_name(self) -> str:
        return data.save_name_for_title(self.name_edit.text())

    def accept(self) -> None:
        name = self.save_name
        if os.path.exists(data.game_file(name, data.saves_dir())) and not question_dialog(
            self, _('Save already exists'), _('A saved game named "{}" already exists. Replace it?').format(name)
        ):
            return
        super().accept()


class LoadGameDialog(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Load a saved game'), 'cyoa-load-game', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.saves_label = la = QLabel(_('Choose the &saved game to load:'))
        self.saves_list = sl = QListWidget(self)
        la.setBuddy(sl)
        sl.itemActivated.connect(self.accept)
        l.addWidget(la), l.addWidget(sl)
        self.manage_button = mb = QPushButton(QIcon.ic('config.png'), _('&Manage saves'), self)
        mb.setToolTip('<p>' + _('Browse and delete previously saved games'))
        mb.clicked.connect(self.manage_saves)
        self.bb.addButton(mb, QDialogButtonBox.ButtonRole.ActionRole)
        l.addWidget(self.bb)
        self.re_populate()

    def re_populate(self) -> None:
        self.saves_list.clear()
        for e in data.list_games(base=data.saves_dir()):
            turns = ngettext('{} turn', '{} turns', e.num_turns).format(e.num_turns)
            i = QListWidgetItem(f'{e.title} — {turns} — {fmt_timestamp(e.updated)}', self.saves_list)
            i.setData(SAVE_NAME_ROLE, e.game_id)
        self.saves_list.setCurrentRow(0)

    def manage_saves(self) -> None:
        ManageSavesDialog(self).exec()
        self.re_populate()

    @property
    def save_name(self) -> str:
        item = self.saves_list.currentItem()
        return str(item.data(SAVE_NAME_ROLE)) if item is not None else ''

    def accept(self) -> None:
        if not self.save_name:
            error_dialog(self, _('No save selected'), _('There are no saved games to load.'), show=True)
            return
        super().accept()
