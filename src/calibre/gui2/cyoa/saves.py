#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The dialogs the player uses to save a game, load a saved game and manage the
# games they have saved. A saved game lives in a folder of cyoa/saves named
# after the name the player chose for it, see calibre.gui2.cyoa.data. It can
# also be exported to a single file with the .calibre-cyoa extension, which
# holds the whole game, pictures and all, so that the player can keep it
# outside the calibre configuration, move it to another computer or pass it on
# to somebody else, see data.export_game() and data.import_game().

import os
from collections.abc import Callable
from contextlib import suppress
from time import localtime, strftime

from qt.core import QDialogButtonBox, QIcon, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, Qt, QVBoxLayout, QWidget

from calibre.ai.cyoa import GameState
from calibre.gui2 import choose_files, choose_save_file, error_dialog, info_dialog, question_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _, ngettext

SAVE_NAME_ROLE = Qt.ItemDataRole.UserRole


def fmt_timestamp(ts: float) -> str:
    return strftime('%d %b %Y, %H:%M', localtime(ts))


def save_entry_text(e: data.SavedGame) -> str:
    # A game in the saves folder lives in a folder named after the name the
    # player chose when saving it, so that, and not the title of the world the
    # game happens to be set in, is what identifies the save to them.
    turns = ngettext('{} turn', '{} turns', e.num_turns).format(e.num_turns)
    text = f'{e.game_id} — {turns} — {fmt_timestamp(e.updated)}'
    if e.title and e.title != e.game_id:
        text += f' ({e.title})'
    return text


def has_saved_games() -> bool:
    return bool(data.list_games(base=data.saves_dir()))


def populate_saves_list(sl: QListWidget) -> None:
    sl.clear()
    for e in data.list_games(base=data.saves_dir()):
        i = QListWidgetItem(save_entry_text(e), sl)
        i.setData(SAVE_NAME_ROLE, e.game_id)


def select_save(sl: QListWidget, name: str) -> None:
    for row in range(sl.count()):
        if (item := sl.item(row)) is not None and str(item.data(SAVE_NAME_ROLE)) == name:
            sl.setCurrentRow(row)
            return


def selected_save(sl: QListWidget) -> str:
    item = sl.currentItem()
    return str(item.data(SAVE_NAME_ROLE)) if item is not None else ''


def add_action_button(d: Dialog, icon_name: str, text: str, tooltip: str, slot: Callable[[], None]) -> QPushButton:
    # The dialogs that work with saved games put their actions in the button
    # box, alongside the standard buttons.
    b = QPushButton(QIcon.ic(icon_name), text, d)
    b.setToolTip('<p>' + tooltip)
    b.clicked.connect(slot)
    d.bb.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
    return b


def add_manage_saves_button(d: Dialog, slot: Callable[[], None]) -> QPushButton:
    return add_action_button(d, 'config.png', _('&Manage saves'), _('Browse, export and delete previously saved games'), slot)


# Exporting and importing {{{


def export_file_filters() -> list[tuple[str, list[str]]]:
    return [(_('calibre adventure games'), [data.EXPORT_EXTENSION])]


def export_game_to_file(
    parent: QWidget,
    name: str,
    state: GameState,
    images: dict[int, data.SceneImage],
    portraits: dict[str, dict[str, str]],
    created: float = 0,
) -> bool:
    # Ask the player where the exported game should go and write all of it there.
    dest = choose_save_file(
        parent, 'cyoa-export-game', _('Export the game as'), filters=export_file_filters(), initial_filename=f'{name}.{data.EXPORT_EXTENSION}'
    )
    if not dest:
        return False
    if not dest.lower().endswith('.' + data.EXPORT_EXTENSION):
        dest += '.' + data.EXPORT_EXTENSION
    try:
        data.export_game(dest, state, images, portraits, name=name, created=created)
    except Exception:
        import traceback

        # A half written export is worse than none at all, the player has no
        # way of telling it apart from a good one until they try to import it.
        with suppress(OSError):
            os.remove(dest)
        error_dialog(
            parent,
            _('Failed to export game'),
            _('Failed to export the game to {}. Click "Show details" for more information.').format(dest),
            det_msg=traceback.format_exc(),
            show=True,
        )
        return False
    info_dialog(parent, _('Game exported'), _('The game "{0}" was exported to: {1}').format(name, dest), show=True)
    return True


def export_saved_game(parent: QWidget, name: str) -> bool:
    # Export a game from the folder it is saved in, rather than one being played.
    base = data.saves_dir()
    try:
        state, images, portraits = data.load_game(name, base=base)
    except Exception:
        import traceback

        error_dialog(
            parent,
            _('Failed to read game'),
            _('Failed to read the saved game "{}". Click "Show details" for more information.').format(name),
            det_msg=traceback.format_exc(),
            show=True,
        )
        return False
    return export_game_to_file(parent, name, state, images, portraits, data.creation_time(data.game_file(name, base)))


def import_saved_game(parent: QWidget) -> str:
    # Ask the player for a previously exported game and add it to their saved
    # games, returning the name it was saved under, or the empty string if it
    # was not imported.
    paths = choose_files(parent, 'cyoa-import-game', _('Choose the exported game to import'), filters=export_file_filters(), select_only_single_file=True)
    if not paths:
        return ''
    path = paths[0]
    try:
        game = data.import_game(path)
    except Exception as e:
        import traceback

        error_dialog(parent, _('Failed to import game'), _('Failed to import a game from {0}: {1}').format(path, e), det_msg=traceback.format_exc(), show=True)
        return ''
    base = data.saves_dir()
    name = game.name
    if os.path.exists(data.game_file(name, base)) and not question_dialog(
        parent,
        _('Saved game exists'),
        _('A saved game named "{}" already exists. Replace it with the imported game, or keep both?').format(name),
        yes_text=_('&Replace it'),
        no_text=_('&Keep both'),
    ):
        name = data.unique_save_name(name, base)
    try:
        data.save_game(name, game.state, game.images, base=base, portraits=game.portraits)
    except Exception:
        import traceback

        error_dialog(
            parent,
            _('Failed to import game'),
            _('Failed to store the imported game as "{}". Click "Show details" for more information.').format(name),
            det_msg=traceback.format_exc(),
            show=True,
        )
        return ''
    return name


# }}}


class ManageSavesDialog(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Manage saved games'), 'cyoa-manage-saves', parent, default_buttons=QDialogButtonBox.StandardButton.Close)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.saves_label = la = QLabel(_('&Saved games:'))
        self.saves_list = sl = QListWidget(self)
        la.setBuddy(sl)
        l.addWidget(la), l.addWidget(sl)
        self.export_button = add_action_button(
            self, 'save.png', _('&Export'), _('Export the selected saved game to a file you can keep, move to another computer or share'), self.export_selected
        )
        self.delete_button = add_action_button(self, 'trash.png', _('&Delete'), _('Permanently delete the selected saved game'), self.delete_selected)
        l.addWidget(self.bb)
        self.re_populate()

    def re_populate(self) -> None:
        populate_saves_list(self.saves_list)

    @property
    def save_name(self) -> str:
        return selected_save(self.saves_list)

    def export_selected(self) -> None:
        if name := self.save_name:
            export_saved_game(self, name)

    def delete_selected(self) -> None:
        if not (name := self.save_name):
            return
        if question_dialog(self, _('Are you sure?'), _('Permanently delete the saved game "{}"? This cannot be undone.').format(name)):
            data.delete_game(name, base=data.saves_dir())
            self.re_populate()


class SaveGameDialog(Dialog):
    def __init__(
        self,
        default_name: str,
        state: GameState,
        images: dict[int, data.SceneImage],
        portraits: dict[str, dict[str, str]],
        created: float = 0,
        parent: QWidget | None = None,
    ) -> None:
        # The game is needed in full because the export button writes out the
        # game as it is being played, not the last state of it on disk.
        self.default_name = default_name
        self.state = state
        self.images = images
        self.portraits = portraits
        self.created = created
        super().__init__(_('Save game'), 'cyoa-save-game', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.name_label = la = QLabel(_('&Name for this save:'))
        self.name_edit = ne = QLineEdit(self)
        ne.setText(self.default_name)
        ne.setToolTip('<p>' + _('The save is stored in a folder of this name, so characters not allowed in file names are replaced'))
        la.setBuddy(ne)
        l.addWidget(la), l.addWidget(ne)
        self.export_button = add_action_button(
            self, 'save.png', _('&Export'), _('Export this game to a file you can keep, move to another computer or share'), self.export_game
        )
        self.manage_button = add_manage_saves_button(self, self.manage_saves)
        l.addWidget(self.bb)

    def manage_saves(self) -> None:
        ManageSavesDialog(self).exec()

    def export_game(self) -> None:
        # Exporting is not saving, so the dialog stays open afterwards and the
        # player can still save the game, or not, as they please.
        export_game_to_file(self, self.save_name, self.state, self.images, self.portraits, self.created)

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
        self.import_button = add_action_button(
            self, 'document-import.png', _('&Import'), _('Add a previously exported game to your saved games'), self.import_game
        )
        self.manage_button = add_manage_saves_button(self, self.manage_saves)
        l.addWidget(self.bb)
        self.re_populate()

    def re_populate(self, current: str = '') -> None:
        populate_saves_list(self.saves_list)
        self.saves_list.setCurrentRow(0)
        if current:
            select_save(self.saves_list, current)

    def manage_saves(self) -> None:
        ManageSavesDialog(self).exec()
        self.re_populate(self.save_name)

    def import_game(self) -> None:
        # The imported game becomes the selected one, as importing a game is
        # almost always the prelude to playing it.
        if name := import_saved_game(self):
            self.re_populate(name)

    @property
    def save_name(self) -> str:
        return selected_save(self.saves_list)

    def accept(self) -> None:
        if not self.save_name:
            error_dialog(
                self, _('No save selected'), _('There are no saved games to load. Use the Import button to add a previously exported game.'), show=True
            )
            return
        super().accept()
