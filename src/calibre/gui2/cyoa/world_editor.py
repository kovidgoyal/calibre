#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from base64 import standard_b64decode
from collections.abc import Sequence
from itertools import count
from threading import Thread

from qt.core import QGridLayout, QHBoxLayout, QIcon, QLabel, QListWidget, QPlainTextEdit, QSize, Qt, QTabWidget, QVBoxLayout, QWidget, pyqtSignal, sip

from calibre.ai.cyoa import MAX_MAJOR_EVENTS, PROTAGONIST_ID, CharacterState, GameState, PlayerCharacter, StorySummary, clean_text_list
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.world import CharacterEditor, MarkdownEdit, PortraitResult, generate_portrait
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _


class LineListEdit(QPlainTextEdit):
    # Edits an ordered list of short entries, one entry per line. Blank and
    # duplicate lines are discarded when the list is read back, just as they
    # are in the lists the AI sends.

    def load(self, items: Sequence[str]) -> None:
        self.setPlainText('\n'.join(items))

    @property
    def items(self) -> tuple[str, ...]:
        return clean_text_list(self.toPlainText().splitlines())


class StoryMemoryEditor(QWidget):
    # Edits the story summary as it stands at the current turn: the world,
    # the current situation and the lists of past and upcoming events. That
    # summary, together with the characters edited on the other tab of
    # EditWorldDialog, is everything the AI remembers of the story beyond the
    # prose of the current chapter, so editing it steers the story far more
    # directly than rewinding does.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.msg_label = la = QLabel(
            _(
                'The story memory is all the AI remembers of the story beyond the prose of the current chapter,'
                ' so editing it is the most direct way to steer where the story goes next. Changes take effect from'
                ' the next turn and are stored with the current turn, so going back to an earlier turn restores the'
                ' memory as it was then.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)
        self.grid = g = QGridLayout()
        g.setColumnStretch(0, 1), g.setColumnStretch(1, 1)
        l.addLayout(g, stretch=1)
        self.world_edit = MarkdownEdit(self)
        self.add_field(
            0,
            0,
            _('&World:'),
            self.world_edit,
            _('The world the story happens in and its current state. The AI updates this as the story changes the world.'),
        )
        self.current_situation_edit = MarkdownEdit(self)
        self.add_field(
            0,
            1,
            _('Current &situation:'),
            self.current_situation_edit,
            _('Where the protagonist is and what is happening as the story stands. The next turn continues from here.'),
        )
        self.major_events_edit = LineListEdit(self)
        self.add_field(
            1,
            0,
            _('&Major events:'),
            self.major_events_edit,
            _(
                'The major events of the story so far, in chronological order, one per line. At most {} are remembered,'
                ' so combine older events into a single line rather than letting the list grow without end.'
            ).format(MAX_MAJOR_EVENTS),
        )
        self.upcoming_events_edit = LineListEdit(self)
        self.add_field(
            1,
            1,
            _('&Upcoming events:'),
            self.upcoming_events_edit,
            _(
                'Foreshadowed or planned future events and unresolved plot threads, one per line. The AI is asked to pay'
                ' these off as the story goes on, so this is the most direct way to plan what happens next.'
            ),
        )

    def add_field(self, row: int, col: int, label: str, editor: QWidget, tooltip: str) -> None:
        la = QLabel(label)
        la.setBuddy(editor)
        editor.setToolTip('<p>' + tooltip)
        la.setToolTip(editor.toolTip())
        self.grid.addWidget(la, 2 * row, col)
        self.grid.addWidget(editor, 2 * row + 1, col)
        self.grid.setRowStretch(2 * row + 1, 1)

    def load(self, summary: StorySummary) -> None:
        self.world_edit.load(summary.world)
        self.current_situation_edit.load(summary.current_situation)
        self.major_events_edit.load(summary.major_events)
        self.upcoming_events_edit.load(summary.upcoming_events)

    @property
    def validation_error(self) -> str:
        # The AI sends only what a turn changed and whatever it leaves empty
        # is carried over from this summary, so an empty world or situation
        # makes the next turn fail, see updated_summary().
        if not self.world_edit.markdown:
            return _('The description of the world cannot be empty, the AI needs it to continue the story.')
        if not self.current_situation_edit.markdown:
            return _('The current situation cannot be empty, the AI continues the story from it.')
        if (num := len(self.major_events_edit.items)) > MAX_MAJOR_EVENTS:
            return _('The story memory holds at most {0} major events, but {1} are listed. Combine or remove some of them.').format(MAX_MAJOR_EVENTS, num)
        return ''

    def updated(self, summary: StorySummary) -> StorySummary:
        # The characters of the summary are edited on the characters tab and
        # applied separately, so they are left untouched here.
        return summary._replace(
            world=self.world_edit.markdown,
            major_events=self.major_events_edit.items,
            current_situation=self.current_situation_edit.markdown,
            upcoming_events=self.upcoming_events_edit.items,
        )


class EditWorldDialog(Dialog):
    # Edits the world of the game in progress, on two tabs. The characters
    # tab lists the character the player plays followed by the named
    # characters the AI introduced during play, taken from the story summary,
    # and allows editing their descriptions, backstories and, for the story
    # characters, relationships and current state, as well as (re-)generating
    # their portraits. The story memory tab edits the rest of the summary.
    # The edits are applied to the game state by the caller after the dialog
    # is accepted, via the player_character, npcs, portraits and
    # story_memory attributes.

    portrait_result_received = pyqtSignal(int, int, object)  # (call_number, list row, PortraitResult)

    def __init__(self, state: GameState, portraits: dict[str, dict[str, str]] | None = None, parent: QWidget | None = None) -> None:
        self.player_character = state.character
        # The characters the AI introduced during play, i.e. every character
        # in the story summary other than the player. Each carries the stable
        # id that identifies them, so renaming one here is just a rename.
        pname = state.character.name.strip().casefold()
        self.npcs: list[CharacterState] = [c for c in state.current_summary.characters if c.id != PROTAGONIST_ID and c.name.strip().casefold() != pname]
        # Portraits in stored form ({'mime': ..., 'data': base64}), keyed by
        # the id of the character they depict, with the player's portrait
        # under PROTAGONIST_ID. They all belong to this game alone and are
        # supplied and stored in the game file by the caller.
        self.portraits: dict[str, dict[str, str]] = dict(portraits or {})
        self.art_style = state.art_style
        self.world_description = state.world.world_description
        # The summary of the last played turn, which is the memory the next
        # turn is generated from. Before the first turn has been played there
        # is no stored summary to edit, only one derived from the world.
        self.summary = state.current_summary
        self.can_edit_story_memory = bool(state.turns)
        self.images_enabled = data.images_enabled()
        self.current_idx = -1
        # Portrait generation runs one at a time on a background thread:
        # portrait_call identifies the current generation (results from
        # superseded calls are discarded) and portrait_idx is the list row of
        # the character whose portrait is being generated.
        self.portrait_counter = count(start=1)
        self.portrait_call = -1
        self.portrait_idx = -1
        super().__init__(_('Edit world'), 'cyoa-edit-world', parent)

    def sizeHint(self) -> QSize:
        return QSize(1000, 700)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.tabs = t = QTabWidget(self)
        l.addWidget(t)
        t.addTab(self.create_characters_tab(), QIcon.ic('user_profile.png'), _('&Characters'))
        self.memory_editor = me = StoryMemoryEditor(self)
        me.load(self.summary)
        t.addTab(me, QIcon.ic('notes.png'), _('Story &memory'))
        if not self.can_edit_story_memory:
            idx = t.indexOf(me)
            t.setTabEnabled(idx, False)
            t.setTabToolTip(idx, '<p>' + _('The story memory can be edited once the first turn of the story has been played'))
        self.status_label = sl = QLabel('')
        sl.setWordWrap(True)
        l.addWidget(sl)
        l.addWidget(self.bb)
        self.portrait_result_received.connect(self.on_portrait_result, type=Qt.ConnectionType.QueuedConnection)
        self.char_list.setCurrentRow(0)

    def create_characters_tab(self) -> QWidget:
        w = QWidget(self)
        l = QVBoxLayout(w)
        self.msg_label = la = QLabel(
            _(
                'Edit the characters of the story as needed, changes take effect from the next turn.'
                ' Note that editing a character that has already interacted with the world for a while'
                ' is not recommended, as the changes can contradict the story so far.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)
        h = QHBoxLayout()
        self.char_list = cw = QListWidget(w)
        for row in range(1 + len(self.npcs)):
            cw.addItem(self.display_name(row))
        cw.currentRowChanged.connect(self.on_character_changed)
        h.addWidget(cw, stretch=1)
        self.character_editor = ce = CharacterEditor(w)
        ce.set_portrait_ui_visible(self.images_enabled)
        ce.portrait_refresh_requested.connect(self.regenerate_current_portrait)
        h.addWidget(ce, stretch=3)
        l.addLayout(h)
        return w

    def name_for_row(self, row: int) -> str:
        if row == 0:
            return self.player_character.name
        return self.npcs[row - 1].name if 0 < row <= len(self.npcs) else ''

    def display_name(self, row: int) -> str:
        return _('{} (you)').format(self.name_for_row(row)) if row == 0 else self.name_for_row(row)

    def id_for_row(self, row: int) -> str:
        # The stable id under which the portrait of the character in the
        # specified row is stored, empty when they have none.
        if row == 0:
            return PROTAGONIST_ID
        return self.npcs[row - 1].id if 0 < row <= len(self.npcs) else ''

    def commit_character_edits(self) -> None:
        row = self.current_idx
        if row == 0:
            self.player_character = self.character_editor.character
        elif 0 < row <= len(self.npcs):
            self.npcs[row - 1] = self.character_editor.character_state
        else:
            return
        item = self.char_list.item(row)
        if item is not None and self.name_for_row(row):
            item.setText(self.display_name(row))

    def on_character_changed(self, row: int) -> None:
        if row == self.current_idx:
            return
        self.commit_character_edits()
        self.current_idx = row
        if row == 0:
            self.character_editor.load(self.player_character)
        elif 0 < row <= len(self.npcs):
            self.character_editor.load_state(self.npcs[row - 1])
        self.character_editor.set_story_fields_visible(row > 0)
        self.update_portrait_display()
        self.maybe_generate_portrait()

    def row_can_have_portrait(self, row: int) -> bool:
        # A portrait is keyed by the id of the character it depicts, so a
        # character without one, which only a broken AI response can produce,
        # cannot have a portrait stored for them.
        return bool(self.id_for_row(row))

    def portrait_for_row(self, row: int) -> dict[str, str] | None:
        return self.portraits.get(self.id_for_row(row))

    def store_portrait(self, row: int, portrait: dict[str, str] | None) -> None:
        if portrait is not None and (cid := self.id_for_row(row)):
            self.portraits[cid] = portrait

    def character_for_row(self, row: int) -> PlayerCharacter:
        if row == 0:
            return self.player_character
        c = self.npcs[row - 1]
        return PlayerCharacter(name=c.name, description=c.description, backstory=c.backstory)

    def update_portrait_display(self) -> None:
        if not self.images_enabled:
            return
        row = self.current_idx
        if row > -1 and row == self.portrait_idx:
            self.character_editor.show_portrait_busy(True)
            return
        self.character_editor.show_portrait_busy(False)
        p = self.portrait_for_row(row)
        self.character_editor.set_portrait(standard_b64decode(p['data']) if p else None)

    def maybe_generate_portrait(self) -> None:
        # Portraits of characters introduced during play are generated on
        # demand, the first time their page is opened in this dialog.
        row = self.current_idx
        if self.images_enabled and self.portrait_idx == -1 and self.row_can_have_portrait(row) and self.portrait_for_row(row) is None:
            self.start_portrait_generation(row)

    def regenerate_current_portrait(self) -> None:
        self.commit_character_edits()
        if self.portrait_idx > -1:
            self.status_label.setText(_('A portrait is already being generated, please wait.'))
            return
        self.start_portrait_generation(self.current_idx)

    def start_portrait_generation(self, row: int) -> None:
        if not self.images_enabled or not self.row_can_have_portrait(row):
            return
        plugin = data.plugin_for('image')
        if plugin is None:
            return
        self.status_label.setText('')
        self.portrait_call = next(self.portrait_counter)
        self.portrait_idx = row
        Thread(
            name='CYOACharacterPortrait', daemon=True, target=self.do_generate_portrait, args=(self.character_for_row(row), row, self.portrait_call, plugin)
        ).start()
        self.update_portrait_display()

    def do_generate_portrait(self, character: PlayerCharacter, row: int, call_number: int, plugin: AIProviderPlugin) -> None:
        try:
            pr = generate_portrait(character, self.art_style, self.world_description, plugin)
            if sip.isdeleted(self):
                return
            self.portrait_result_received.emit(call_number, row, pr)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_portrait_result(self, call_number: int, row: int, pr: PortraitResult) -> None:
        if call_number != self.portrait_call:
            return  # a stale result from a superseded or cancelled call
        self.portrait_call = -1
        self.portrait_idx = -1
        if pr.error:
            self.status_label.setText(_('Failed to generate a portrait for {0}: {1}').format(self.name_for_row(row), pr.error))
            self.status_label.setToolTip(pr.error_details)
        else:
            self.store_portrait(row, pr.portrait)
        self.update_portrait_display()
        # the player may have switched to another character without a
        # portrait while this one was being generated
        self.maybe_generate_portrait()

    @property
    def story_memory(self) -> StorySummary | None:
        # The edited summary, with its characters left as they were: those
        # are edited on the characters tab and applied to every turn rather
        # than only to the current one. None when there is no stored summary
        # to edit because the story has not begun.
        return self.memory_editor.updated(self.summary) if self.can_edit_story_memory else None

    def accept(self) -> None:
        self.commit_character_edits()
        if not self.player_character.name or any(not c.name for c in self.npcs):
            self.tabs.setCurrentIndex(0)
            error_dialog(self, _('No character name'), _('Every character must have a name.'), show=True)
            return
        if self.can_edit_story_memory and (err := self.memory_editor.validation_error):
            self.tabs.setCurrentWidget(self.memory_editor)
            error_dialog(self, _('Story memory is incomplete'), err, show=True)
            return
        super().accept()
