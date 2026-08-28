#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The world creation flow for the "Create Your Own Adventure" game: choose a
# pre-made world or describe your own, have the AI expand it into a full
# world with playable characters, then customize the world and choose the
# character to play as.

from itertools import count
from threading import Thread
from typing import NamedTuple

from qt.core import (
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    Qt,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.ai import StructuredOutputResult
from calibre.ai.cyoa import GeneratedWorld, PlayerCharacter, generate_world
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.progress_indicator import WaitStack
from calibre.utils.localization import _, pgettext


class PremadeWorld(NamedTuple):
    title: str
    brief: str


# The briefs are prompts sent to the AI and are deliberately not translated,
# as AI models work best with English instructions.
PREMADE_WORLDS = (
    PremadeWorld(
        _('Epic fantasy'),
        (
            'A vast high fantasy realm of warring kingdoms, ancient forests and forgotten ruins.'
            ' An ancient prophecy is stirring, dragons have been sighted for the first time in centuries,'
            ' and a darkness gathers in the north while the great houses squabble over a fractured throne.'
        ),
    ),
    PremadeWorld(
        _('Space opera'),
        (
            'A far future galaxy dominated by a decaying stellar empire and a scrappy rebel alliance.'
            ' Faster-than-light travel runs on mysterious alien artifacts nobody fully understands,'
            ' and a newly discovered artifact at the galactic rim could change the balance of power forever.'
        ),
    ),
    PremadeWorld(
        _('Cyberpunk noir'),
        (
            'A rain-soaked megacity of neon, chrome and corporate arcologies, where AIs pull strings'
            ' from the shadows and memories can be bought and sold. Street-level hustlers, jaded'
            " detectives and rogue programs all chase the same secret buried in the city's oldest network."
        ),
    ),
    PremadeWorld(
        _('Post-apocalyptic survival'),
        (
            'A century after civilization collapsed, scattered settlements cling to life amid ruined'
            ' cities, toxic zones and mutated wilderness. Water and fuel are currency, raiders prowl'
            ' the old highways, and rumors spread of a pre-collapse vault that could restore the world.'
        ),
    ),
    PremadeWorld(
        _('Pirate adventure'),
        (
            'The golden age of piracy on a chain of tropical islands, with treasure fleets, naval'
            ' patrols, smuggler coves and legends of cursed gold. A recently surfaced map promises'
            ' the hoard of a legendary pirate king, and every crew in the islands wants it.'
        ),
    ),
    PremadeWorld(
        _('Gothic horror'),
        (
            'A remote Victorian estate on the windswept moors, full of locked rooms, family secrets'
            ' and things that walk at night. The new heir has just arrived to claim an inheritance'
            ' that the villagers whisper is cursed, and the house itself seems to be watching.'
        ),
    ),
    PremadeWorld(
        _('Murder mystery'),
        (
            'A snowbound 1920s country house party where the host is found dead on the first night.'
            ' Every guest has a motive, the telephone lines are down, and the killer must be found'
            ' before the snow melts and they slip away.'
        ),
    ),
    PremadeWorld(
        _('Wild West'),
        (
            'A dusty frontier town at the edge of the gold fields, caught between a ruthless cattle'
            ' baron, a crooked railroad company and the last honest lawman. Fortunes are made and'
            ' lost overnight, and every stranger riding in brings trouble with them.'
        ),
    ),
    PremadeWorld(
        _('Greek mythology'),
        (
            'The age of heroes in mythic Greece, where the gods of Olympus meddle in mortal affairs,'
            ' monsters haunt the wine-dark sea and glory is won through impossible quests. An oracle'
            ' has spoken of a deed that could earn a mortal a place among the stars.'
        ),
    ),
    PremadeWorld(
        _('Regency intrigue'),
        (
            'London high society at the height of the Regency era: glittering balls, arranged'
            ' marriages, ruinous gossip and fortunes won at the card table. Beneath the polished'
            ' manners, a scandal is brewing that could topple one of the great families.'
        ),
    ),
)

BRIEF_ROLE = Qt.ItemDataRole.UserRole
SAVED_WORLD_ROLE = Qt.ItemDataRole.UserRole + 1


class CharacterEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QFormLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_edit = QLineEdit(self)
        l.addRow(pgettext('name of a character in a story', '&Name:'), self.name_edit)
        self.description_edit = QPlainTextEdit(self)
        l.addRow(_('&Description:'), self.description_edit)
        self.backstory_edit = QPlainTextEdit(self)
        l.addRow(_('&Backstory:'), self.backstory_edit)

    def load(self, c: PlayerCharacter) -> None:
        self.name_edit.setText(c.name)
        self.description_edit.setPlainText(c.description)
        self.backstory_edit.setPlainText(c.backstory)

    @property
    def character(self) -> PlayerCharacter:
        return PlayerCharacter(
            name=self.name_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            backstory=self.backstory_edit.toPlainText().strip(),
        )


class WorldEditWidget(QWidget):
    start_requested = pyqtSignal(object, object)  # (GeneratedWorld, PlayerCharacter)
    back_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.brief = ''
        self.characters: list[PlayerCharacter] = []
        self.current_char_idx = -1
        l = QVBoxLayout(self)
        la = QLabel(_('Customize the world to your liking, then select the character you will play as and edit them as needed.'))
        la.setWordWrap(True)
        l.addWidget(la)

        h = QHBoxLayout()
        tl = QLabel(_('&Title:'))
        self.title_edit = te = QLineEdit(self)
        tl.setBuddy(te)
        h.addWidget(tl), h.addWidget(te)
        l.addLayout(h)

        wl = QLabel(_('&World description:'))
        self.world_edit = we = QPlainTextEdit(self)
        wl.setBuddy(we)
        l.addWidget(wl), l.addWidget(we)

        cl = QLabel(_('Win &condition:'))
        self.win_edit = wc = QPlainTextEdit(self)
        wc.setMaximumHeight(wc.fontMetrics().lineSpacing() * 4)
        cl.setBuddy(wc)
        l.addWidget(cl), l.addWidget(wc)

        chl = QLabel(_('Choose the character you will &play as:'))
        l.addWidget(chl)
        h = QHBoxLayout()
        self.char_list = cw = QListWidget(self)
        chl.setBuddy(cw)
        cw.currentRowChanged.connect(self.on_character_changed)
        h.addWidget(cw, stretch=1)
        self.character_editor = ce = CharacterEditor(self)
        h.addWidget(ce, stretch=3)
        l.addLayout(h)

        h = QHBoxLayout()
        self.back_button = bb = QPushButton(QIcon.ic('back.png'), _('&Back'), self)
        bb.setToolTip('<p>' + _('Go back and generate a different world'))
        bb.clicked.connect(self.back_requested)
        h.addWidget(bb)
        self.save_button = sb = QPushButton(QIcon.ic('save.png'), _('&Save world for later'), self)
        sb.setToolTip('<p>' + _('Save this world so you can play more adventures in it later without re-generating it'))
        sb.clicked.connect(self.save_world)
        h.addWidget(sb)
        self.status_label = st = QLabel('')
        st.setWordWrap(True)
        h.addWidget(st, stretch=10)
        self.start_button = pb = QPushButton(QIcon.ic('ok.png'), _('Start &playing'), self)
        pb.clicked.connect(self.start_game)
        h.addWidget(pb)
        l.addLayout(h)

    def load(self, brief: str, world: GeneratedWorld) -> None:
        self.brief = brief
        self.current_char_idx = -1
        self.characters = list(world.characters)
        self.title_edit.setText(world.title)
        self.world_edit.setPlainText(world.world_description)
        self.win_edit.setPlainText(world.win_condition)
        self.char_list.clear()
        for c in self.characters:
            self.char_list.addItem(c.name)
        if self.characters:
            self.char_list.setCurrentRow(0)

    def show_status(self, text: str) -> None:
        self.status_label.setText(text)

    def commit_character_edits(self) -> None:
        if -1 < self.current_char_idx < len(self.characters):
            c = self.character_editor.character
            self.characters[self.current_char_idx] = c
            item = self.char_list.item(self.current_char_idx)
            if item is not None and c.name:
                item.setText(c.name)

    def on_character_changed(self, row: int) -> None:
        if row == self.current_char_idx:
            return
        self.commit_character_edits()
        self.current_char_idx = row
        if -1 < row < len(self.characters):
            self.character_editor.load(self.characters[row])

    @property
    def current_world(self) -> GeneratedWorld:
        self.commit_character_edits()
        return GeneratedWorld(
            title=self.title_edit.text().strip(),
            world_description=self.world_edit.toPlainText().strip(),
            characters=tuple(self.characters),
            win_condition=self.win_edit.toPlainText().strip(),
        )

    def save_world(self) -> None:
        data.add_saved_world(self.brief, self.current_world)
        self.show_status(_('World saved. You can select it when creating future adventures.'))

    def start_game(self) -> None:
        w = self.current_world
        if not w.title:
            return error_dialog(self, _('No title'), _('The world must have a title.'), show=True)
        if not w.world_description:
            return error_dialog(self, _('No world description'), _('The world must have a description.'), show=True)
        if not w.win_condition:
            return error_dialog(
                self, _('No win condition'), _('The world must have a win condition, otherwise the adventure can never be completed.'), show=True
            )
        row = self.char_list.currentRow()
        if not w.characters or not (-1 < row < len(w.characters)):
            return error_dialog(self, _('No character selected'), _('Select the character you will play as.'), show=True)
        c = w.characters[row]
        if not c.name:
            return error_dialog(self, _('No character name'), _('The character you play as must have a name.'), show=True)
        self.start_requested.emit(w, c)


class CreateWorldWidget(QWidget):
    result_received = pyqtSignal(int, object)
    game_start_requested = pyqtSignal(object, object, str)  # (GeneratedWorld, PlayerCharacter, brief)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.counter = count(start=1)
        self.current_call_number = -1
        self.current_brief = ''
        self.stack = s = QStackedLayout(self)

        self.brief_page = bp = QWidget(self)
        bl = QVBoxLayout(bp)
        la = QLabel(
            _(
                'Choose one of the pre-made worlds below, or describe the world for your adventure'
                ' in your own words. Selecting a pre-made world fills in its description, which you'
                ' can edit freely. When you are happy with the description, click <b>Generate world</b>'
                ' and the AI will expand it into a full game world with characters to play as.'
            )
        )
        la.setWordWrap(True)
        bl.addWidget(la)
        h = QHBoxLayout()
        self.worlds_list = wli = QListWidget(bp)
        wli.currentItemChanged.connect(self.on_world_selected)
        wli.itemActivated.connect(self.on_world_activated)
        h.addWidget(wli, stretch=1)
        v = QVBoxLayout()
        pl = QLabel(_('&World description:'))
        self.prompt_edit = pe = QPlainTextEdit(bp)
        pe.setPlaceholderText(_('Describe the world for your adventure'))
        pl.setBuddy(pe)
        v.addWidget(pl), v.addWidget(pe)
        bh = QHBoxLayout()
        self.generate_button = gb = QPushButton(QIcon.ic('ai.png'), _('&Generate world'), bp)
        gb.clicked.connect(self.start_generation)
        bh.addWidget(gb), bh.addStretch()
        v.addLayout(bh)
        h.addLayout(v, stretch=2)
        bl.addLayout(h)
        self.populate_worlds_list()

        self.wait_stack = ws = WaitStack(_('Creating your world, this can take a while…'), after=bp, parent=self, size=128)
        ws.stop()
        s.addWidget(ws)

        self.world_edit = we = WorldEditWidget(self)
        we.start_requested.connect(self.on_start_requested)
        we.back_requested.connect(self.show_brief_page)
        s.addWidget(we)

        self.result_received.connect(self.on_result, type=Qt.ConnectionType.QueuedConnection)

    def populate_worlds_list(self) -> None:
        self.worlds_list.clear()
        for pw in PREMADE_WORLDS:
            i = QListWidgetItem(pw.title, self.worlds_list)
            i.setData(BRIEF_ROLE, pw.brief)
        saved = data.saved_worlds()
        if saved:
            sep = QListWidgetItem(_('Previously created worlds:'), self.worlds_list)
            sep.setFlags(Qt.ItemFlag.NoItemFlags)
            for idx, entry in enumerate(saved):
                title = (entry.get('world') or {}).get('title') or _('Untitled world')
                i = QListWidgetItem(title, self.worlds_list)
                i.setToolTip('<p>' + _('A world you created previously. Activate it to play in it without re-generating it.'))
                i.setData(BRIEF_ROLE, entry.get('brief') or '')
                i.setData(SAVED_WORLD_ROLE, idx)

    def on_world_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is not None and current.data(SAVED_WORLD_ROLE) is None:
            if brief := current.data(BRIEF_ROLE):
                self.prompt_edit.setPlainText(brief)

    def on_world_activated(self, item: QListWidgetItem) -> None:
        idx = item.data(SAVED_WORLD_ROLE)
        if idx is None:
            return
        try:
            entry = data.saved_worlds()[idx]
            world = data.world_from_saved(entry)
        except Exception as e:
            error_dialog(self, _('Corrupted saved world'), _('Failed to load the saved world: {}').format(e), show=True)
            return
        self.current_brief = entry.get('brief') or ''
        self.world_edit.load(self.current_brief, world)
        self.world_edit.show_status('')
        self.stack.setCurrentWidget(self.world_edit)

    def show_brief_page(self) -> None:
        self.current_call_number = -1  # cancels any in-flight generation
        self.wait_stack.stop()
        self.populate_worlds_list()
        self.stack.setCurrentWidget(self.wait_stack)

    def reset(self) -> None:
        self.show_brief_page()

    def start_generation(self) -> None:
        brief = self.prompt_edit.toPlainText().strip()
        if not brief:
            error_dialog(self, _('No world description'), _('Describe the world you want to play in, or choose one of the pre-made worlds.'), show=True)
            return
        plugin = data.plugin_for('text')
        if plugin is None:
            error_dialog(self, _('No AI configured'), _('No AI for text generation has been configured for the game.'), show=True)
            return
        self.current_brief = brief
        self.current_call_number = next(self.counter)
        self.wait_stack.start()
        Thread(name='CYOAWorldGen', daemon=True, target=self.do_generate, args=(brief, self.current_call_number, plugin)).start()

    def do_generate(self, brief: str, call_number: int, plugin: AIProviderPlugin) -> None:
        try:
            # the preferences overlay is thread local so must be entered here
            with data.cyoa_ai_settings():
                res = generate_world(brief, plugin)
            if sip.isdeleted(self):
                return
            self.result_received.emit(call_number, res)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_result(self, call_number: int, res: StructuredOutputResult) -> None:
        if call_number != self.current_call_number:
            return  # a stale result from a superseded or cancelled call
        self.wait_stack.stop()
        if res.exception is not None:
            error_dialog(self, _('World generation failed'), _('Failed to generate the world: {}').format(res.exception), det_msg=res.error_details, show=True)
            return
        world = res.data
        if not isinstance(world, GeneratedWorld) or not world.characters:
            error_dialog(self, _('World generation failed'), _('The AI returned an invalid world, try again.'), det_msg=res.raw, show=True)
            return
        self.world_edit.load(self.current_brief, world)
        parts = []
        if res.model:
            parts.append(_('Model: {}').format(res.model))
        if res.cost:
            parts.append(_('Cost: {}').format(f'{res.cost:.4f} {res.currency}'.strip()))
        self.world_edit.show_status(' · '.join(parts))
        self.stack.setCurrentWidget(self.world_edit)

    def on_start_requested(self, world: GeneratedWorld, character: PlayerCharacter) -> None:
        # remember the world so more adventures can be played in it later
        data.add_saved_world(self.world_edit.brief, world)
        self.game_start_requested.emit(world, character, self.world_edit.brief)


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    w = CreateWorldWidget()
    w.game_start_requested.connect(lambda world, character, brief: print('start playing:', world.title, 'as', character.name))
    w.resize(900, 600)
    w.show()
    app.exec()
    del w
    del app
