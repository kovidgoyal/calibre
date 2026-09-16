#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The world creation flow for the "Create Your Own Adventure" game: choose a
# pre-made world or describe your own, have the AI expand it into a full
# world, customize that world, then have the AI create the cast of characters
# that live in it, edit them and choose the one to play as. The cast is
# generated after the world has been edited, rather than with it, so that the
# characters fit the world as the player settled on it.

from base64 import standard_b64decode, standard_b64encode
from collections.abc import Sequence
from itertools import count
from threading import Thread
from typing import NamedTuple

from qt.core import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPixmap,
    QPlainTextEdit,
    QPushButton,
    QSize,
    QStackedLayout,
    Qt,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.ai import ImageGenerationOptions, StructuredOutputResult
from calibre.ai.cyoa import (
    ART_STYLES,
    NARRATION_STYLES,
    PACES,
    PROTAGONIST_ID,
    TONES,
    ArtStyle,
    CharacterState,
    GeneratedCast,
    GeneratedWorld,
    Narration,
    NonPlayerCharacter,
    Pace,
    PlayerCharacter,
    StoryStyle,
    Tone,
    character_portrait_prompt,
    generate_cast,
    generate_world,
    npc_character_ids,
)
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.saves import LoadGameDialog, has_saved_games
from calibre.gui2.cyoa.text_display import TextDisplay
from calibre.gui2.progress_indicator import WaitStack
from calibre.gui2.widgets2 import Dialog
from calibre.utils.img import image_from_data, image_to_data, resize_to_fit
from calibre.utils.localization import _, pgettext


class PremadeWorld(NamedTuple):
    title: str
    brief: str
    art_style: str  # the key of the recommended art style from calibre.ai.cyoa.ART_STYLES
    # The key of the tone from calibre.ai.cyoa.TONES the world reads best in,
    # empty for the worlds that could be told in any of them, which leaves
    # the choice to the AI.
    tone: str = ''


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
        'digital-painting',
        tone='heroic',
    ),
    PremadeWorld(
        _('Space opera'),
        (
            'A far future galaxy dominated by a decaying stellar empire and a scrappy rebel alliance.'
            ' Faster-than-light travel runs on mysterious alien artifacts nobody fully understands,'
            ' and a newly discovered artifact at the galactic rim could change the balance of power forever.'
        ),
        'digital-painting',
        tone='heroic',
    ),
    PremadeWorld(
        _('Cyberpunk noir'),
        (
            'A rain-soaked megacity of neon, chrome and corporate arcologies, where AIs pull strings'
            ' from the shadows and memories can be bought and sold. Street-level hustlers, jaded'
            " detectives and rogue programs all chase the same secret buried in the city's oldest network."
        ),
        'anime',
        tone='grimdark',
    ),
    PremadeWorld(
        _('Post-apocalyptic survival'),
        (
            'A century after civilization collapsed, scattered settlements cling to life amid ruined'
            ' cities, toxic zones and mutated wilderness. Water and fuel are currency, raiders prowl'
            ' the old highways, and rumors spread of a pre-collapse vault that could restore the world.'
        ),
        'photorealistic',
        tone='grimdark',
    ),
    PremadeWorld(
        _('Pirate adventure'),
        (
            'The golden age of piracy on a chain of tropical islands, with treasure fleets, naval'
            ' patrols, smuggler coves and legends of cursed gold. A recently surfaced map promises'
            ' the hoard of a legendary pirate king, and every crew in the islands wants it.'
        ),
        'comic',
        tone='heroic',
    ),
    PremadeWorld(
        _('Gothic horror'),
        (
            'A remote Victorian estate on the windswept moors, full of locked rooms, family secrets'
            ' and things that walk at night. The new heir has just arrived to claim an inheritance'
            ' that the villagers whisper is cursed, and the house itself seems to be watching.'
        ),
        'noir',
        tone='grimdark',
    ),
    PremadeWorld(
        _('Murder mystery'),
        (
            'A snowbound 1920s country house party where the host is found dead on the first night.'
            ' Every guest has a motive, the telephone lines are down, and the killer must be found'
            ' before the snow melts and they slip away.'
        ),
        'noir',
    ),
    PremadeWorld(
        _('Wild West'),
        (
            'A dusty frontier town at the edge of the gold fields, caught between a ruthless cattle'
            ' baron, a crooked railroad company and the last honest lawman. Fortunes are made and'
            ' lost overnight, and every stranger riding in brings trouble with them.'
        ),
        'photorealistic',
    ),
    PremadeWorld(
        _('Greek mythology'),
        (
            'The age of heroes in mythic Greece, where the gods of Olympus meddle in mortal affairs,'
            ' monsters haunt the wine-dark sea and glory is won through impossible quests. An oracle'
            ' has spoken of a deed that could earn a mortal a place among the stars.'
        ),
        'digital-painting',
        tone='heroic',
    ),
    PremadeWorld(
        _('Abbasid Caliphate'),
        (
            'Baghdad at the height of the Abbasid Caliphate, the glittering heart of the Islamic'
            ' Golden Age: bustling bazaars, the scholars of the House of Wisdom, caravans on the'
            ' Silk Road and palace intrigue in the court of the Caliph. A famed treatise has vanished'
            ' from the House of Wisdom, and whispers in the souk say its loss conceals a plot against the throne.'
        ),
        'digital-painting',
    ),
    PremadeWorld(
        _('Regency intrigue'),
        (
            'London high society at the height of the Regency era: glittering balls, arranged'
            ' marriages, ruinous gossip and fortunes won at the card table. Beneath the polished'
            ' manners, a scandal is brewing that could topple one of the great families.'
        ),
        'watercolor',
        tone='romance',
    ),
)


def style_combo(parent: QWidget, styles: Sequence[ArtStyle | Pace | Tone | Narration], tooltip: str) -> QComboBox:
    # A drop down of one table of styles, with the stable key of each style as
    # the item data, see calibre.ai.cyoa.style_for_key().
    c = QComboBox(parent)
    for style in styles:
        c.addItem(style.name, style.key)
    c.setToolTip('<p>' + tooltip)
    return c


def generation_status(res: StructuredOutputResult) -> str:
    # What an AI call cost the player, shown once its result is in.
    parts = []
    if res.model:
        parts.append(_('Model: {}').format(res.model))
    if res.cost:
        parts.append(_('Cost: {}').format(f'{res.cost:.4f} {res.currency}'.strip()))
    return ' · '.join(parts)


def recommended_style(brief: str) -> StoryStyle:
    # The styles recommended for a brief when it is one of the pre-made
    # worlds. The pace and the narration are a matter of taste rather than of
    # the world, so they are never recommended and are left at the defaults,
    # as are the styles of a world the player described themselves.
    for pw in PREMADE_WORLDS:
        if pw.brief == brief:
            return StoryStyle(art_style=pw.art_style, tone=pw.tone)
    return StoryStyle()


WORLD_GENERATION_MESSAGE = _('Creating your world, this can take a while…')
BRIEF_ROLE = Qt.ItemDataRole.UserRole
SAVED_WORLD_ROLE = Qt.ItemDataRole.UserRole + 1
# Portraits are stored downscaled to fit this size and displayed at half of
# it, keeping the saved world JSON reasonably small while looking sharp even
# on high DPI screens.
PORTRAIT_SIZE = QSize(384, 512)


def padded_portraits(portraits: Sequence[dict[str, str] | None], num_characters: int) -> list[dict[str, str] | None]:
    # The portraits, clamped and padded to exactly one entry per character.
    ans = list(portraits[:num_characters])
    ans.extend([None] * (num_characters - len(ans)))
    return ans


class PortraitResult(NamedTuple):
    # The outcome of generating one character portrait, in the form stored in
    # saved worlds: {'mime': mime type, 'data': base64 encoded image data}.
    portrait: dict[str, str] | None
    style: str  # the art style key the portrait was generated with
    error: str = ''
    error_details: str = ''


def generate_portrait(character: PlayerCharacter, style: str, world_description: str, plugin: AIProviderPlugin) -> PortraitResult:
    # Generate the portrait of a character, blocking, so call it on a
    # background thread. Errors are reported in the result, not raised.
    # the preferences overlay is thread local so must be entered here
    with data.cyoa_ai_settings():
        res = plugin.generate_image(character_portrait_prompt(character, style, world_description), options=ImageGenerationOptions(aspect_ratio='3:4'))
    portrait: dict[str, str] | None = None
    error, error_details = '', ''
    if res.exception is not None:
        error, error_details = str(res.exception), res.error_details
    elif not res.image:
        error = _('The AI did not return an image')
    else:
        try:
            img = resize_to_fit(image_from_data(res.image.data), PORTRAIT_SIZE.width(), PORTRAIT_SIZE.height())[1]
            webp = image_to_data(img, compression_quality=70, fmt='WEBP')
            portrait = {'mime': 'image/webp', 'data': standard_b64encode(webp).decode('ascii')}
        except Exception as e:
            error = str(e)
    return PortraitResult(portrait, style, error, error_details)


class MarkdownEdit(QTextEdit):
    # Edits Markdown text, displaying the formatting rather than the markup

    def load(self, text: str) -> None:
        self.setMarkdown(text)

    @property
    def markdown(self) -> str:
        return self.toMarkdown().strip()


class CharacterEditor(QWidget):
    portrait_refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.form_layout = l = QFormLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_edit = QLineEdit(self)
        l.addRow(pgettext('name of a character in a story', '&Name:'), self.name_edit)
        self.description_edit = MarkdownEdit(self)

        # The AI generated portrait of the character, shown to the right of
        # the description, hidden when no image AI is configured.
        self.portrait_panel = pp = QWidget(self)
        pl = QVBoxLayout(pp)
        pl.setContentsMargins(0, 0, 0, 0)
        self.portrait_label = pla = QLabel(pp)
        pla.setFixedSize(PORTRAIT_SIZE / 2)
        pla.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.portrait_stack = ps = WaitStack(_('Generating…'), after=pla, parent=pp, size=64)
        ps.stop()
        pl.addWidget(ps)
        h = QHBoxLayout()
        self.refresh_portrait_button = rb = QToolButton(pp)
        rb.setIcon(QIcon.ic('view-refresh.png'))
        rb.setAutoRaise(True)
        rb.setToolTip('<p>' + _('Re-generate the portrait using the current description'))
        rb.clicked.connect(self.portrait_refresh_requested)
        h.addStretch(), h.addWidget(rb)
        pl.addLayout(h)
        pl.addStretch()

        dw = QWidget(self)
        dw.setFocusProxy(self.description_edit)
        dl = QHBoxLayout(dw)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(self.description_edit, stretch=1)
        dl.addWidget(pp, alignment=Qt.AlignmentFlag.AlignTop)
        l.addRow(_('&Description:'), dw)
        self.backstory_edit = MarkdownEdit(self)
        l.addRow(_('&Backstory:'), self.backstory_edit)
        # Relationships and current state exist only for characters from the
        # story summary, hidden unless load_state() is used, see
        # set_story_fields_visible().
        self.relationships_edit = MarkdownEdit(self)
        l.addRow(_('&Relationships:'), self.relationships_edit)
        self.current_state_edit = MarkdownEdit(self)
        l.addRow(_('C&urrent state:'), self.current_state_edit)
        self.set_story_fields_visible(False)
        # The stable id of the character loaded by load_state(), which is
        # their identity and so must survive being edited, in particular
        # being renamed.
        self.character_id = ''

    def load(self, c: PlayerCharacter) -> None:
        self.character_id = ''
        self.name_edit.setText(c.name)
        self.description_edit.load(c.description)
        self.backstory_edit.load(c.backstory)

    def load_npc(self, c: NonPlayerCharacter) -> None:
        # Load a character of the world the player will meet but cannot play
        # as. They have relationships with the rest of the cast but no current
        # state: the story they take part in has not begun.
        self.load(PlayerCharacter(name=c.name, description=c.description, backstory=c.backstory))
        self.relationships_edit.load(c.relationships)

    def load_state(self, c: CharacterState) -> None:
        # Load a character of the story summary, which additionally tracks
        # their relationships with the other characters and what is true of
        # them at this point in the story.
        self.load(PlayerCharacter(name=c.name, description=c.description, backstory=c.backstory))
        self.character_id = c.id
        self.relationships_edit.load(c.relationships)
        self.current_state_edit.load(c.current_state)

    def set_story_fields_visible(self, visible: bool, current_state: bool | None = None) -> None:
        # current_state defaults to being shown with the relationships; it is
        # shown separately for the characters of a world that is still being
        # created, who have relationships but no story yet.
        self.form_layout.setRowVisible(self.relationships_edit, visible)
        self.form_layout.setRowVisible(self.current_state_edit, visible if current_state is None else current_state)

    def set_portrait_ui_visible(self, visible: bool) -> None:
        self.portrait_panel.setVisible(visible)

    def show_portrait_busy(self, busy: bool) -> None:
        self.portrait_stack.start() if busy else self.portrait_stack.stop()

    def set_portrait(self, image_data: bytes | None) -> None:
        if not image_data:
            self.portrait_label.setText(_('No portrait'))
            return
        pm = QPixmap()
        pm.loadFromData(image_data)
        dpr = self.devicePixelRatioF()
        pm = pm.scaled(self.portrait_label.size() * dpr, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.portrait_label.setPixmap(pm)

    @property
    def character(self) -> PlayerCharacter:
        return PlayerCharacter(
            name=self.name_edit.text().strip(),
            description=self.description_edit.markdown,
            backstory=self.backstory_edit.markdown,
        )

    @property
    def non_player_character(self) -> NonPlayerCharacter:
        c = self.character
        return NonPlayerCharacter(name=c.name, description=c.description, backstory=c.backstory, relationships=self.relationships_edit.markdown)

    @property
    def character_state(self) -> CharacterState:
        c = self.character
        return CharacterState(
            name=c.name,
            description=c.description,
            backstory=c.backstory,
            relationships=self.relationships_edit.markdown,
            current_state=self.current_state_edit.markdown,
            id=self.character_id,
        )


class WorldEditWidget(QWidget):
    start_requested = pyqtSignal(object, int)  # (GeneratedWorld, index in its characters of the character to play as)
    back_requested = pyqtSignal()
    cast_requested = pyqtSignal(object)  # the GeneratedWorld, as edited, to create the cast of characters for

    portrait_result_received = pyqtSignal(int, int, object)  # (call_number, character index, PortraitResult)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.brief = ''
        # The id of the saved world being edited, empty for a world that has
        # not been saved yet. It identifies the entry to update when saving,
        # so that renaming a world does not orphan it and its portraits.
        self.world_id = ''
        # The cast of the world: the characters the player can choose to play
        # as and the other characters that live in the world, which the player
        # can edit as well. Both are empty until the cast has been generated
        # from the world, which happens after the world has been edited, see
        # cast_requested.
        self.characters: list[PlayerCharacter] = []
        self.npcs: list[NonPlayerCharacter] = []
        # The world description the current cast was generated from, so that a
        # world edited after the cast was created can be noticed, see
        # proceed_to_characters().
        self.cast_source = ''
        self.current_char_idx = -1
        self.images_enabled = False
        # Portraits in stored form ({'mime': ..., 'data': base64} or None)
        # and the art style key each was generated with, aligned with the
        # combined list of characters: the playable characters followed by the
        # non player characters, see character_at(). Generation runs one
        # character at a time on a background thread:
        # portrait_inflight/portrait_call identify the current generation
        # (results from superseded calls are discarded) and portrait_queue
        # holds the characters still to be generated.
        self.portraits: list[dict[str, str] | None] = []
        self.portrait_styles: list[str] = []
        self.portrait_counter = count(start=1)
        self.portrait_call = -1
        self.portrait_inflight = -1
        self.portrait_inflight_style = ''
        self.portrait_queue: list[int] = []
        self.stack = s = QStackedLayout(self)

        self.world_page = wp = QWidget(self)
        l = QVBoxLayout(wp)
        la = QLabel(
            _(
                'Customize the world to your liking. When you are happy with it, the AI will create the'
                ' characters that live in it, for you to edit and to choose the one you play as.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        h = QHBoxLayout()
        tl = QLabel(_('&Title:'))
        self.title_edit = te = QLineEdit(wp)
        tl.setBuddy(te)
        h.addWidget(tl), h.addWidget(te)
        l.addLayout(h)

        wl = QLabel(_('&World description:'))
        self.world_edit = we = MarkdownEdit(wp)
        wl.setBuddy(we)
        l.addWidget(wl), l.addWidget(we)

        h = QHBoxLayout()
        self.art_style_label = asl = QLabel(_('Art style for generated &images:'))
        self.art_style_combo = self.add_style_combo(
            h, asl, ART_STYLES, _('The visual style used when generating pictures for this world, such as character portraits')
        )
        h.addStretch()
        l.addLayout(h)

        # How the AI is to write the prose of the story. Unlike the art style
        # these apply to a text only game as well, so they are always shown.
        h = QHBoxLayout()
        self.pace_combo = self.add_style_combo(
            h,
            QLabel(_('Passage &length:')),
            PACES,
            _('How much prose the AI writes for each turn of the story. Short passages make for a faster, pulpier narrative and cost less to generate.'),
        )
        self.tone_combo = self.add_style_combo(
            h,
            QLabel(_('Story t&one:')),
            TONES,
            _('The register the story is told in. Leave it to the AI and it will pick one that suits the world.'),
        )
        self.narration_combo = self.add_style_combo(h, QLabel(_('&Narration:')), NARRATION_STYLES, _('The point of view and tense the story is written in'))
        h.addStretch()
        l.addLayout(h)

        h = QHBoxLayout()
        self.back_button = bb = QPushButton(QIcon.ic('back.png'), _('&Back'), wp)
        bb.setToolTip('<p>' + _('Go back and generate a different world'))
        bb.clicked.connect(self.back_requested)
        h.addWidget(bb)
        self.save_button = sb = QPushButton(QIcon.ic('save.png'), _('&Save world for later'), wp)
        sb.setToolTip('<p>' + _('Save this world so you can play more adventures in it later without re-generating it'))
        sb.clicked.connect(self.save_world)
        h.addWidget(sb)
        self.status_label = st = QLabel('')
        st.setWordWrap(True)
        h.addWidget(st, stretch=10)
        self.next_button = nb = QPushButton(QIcon.ic('forward.png'), _('Choose &character'), wp)
        nb.clicked.connect(self.proceed_to_characters)
        h.addWidget(nb)
        l.addLayout(h)
        s.addWidget(wp)

        self.character_page = cp = QWidget(self)
        l = QVBoxLayout(cp)
        la = QLabel(_('Choose the character you will play as. You can edit any of the characters of this world as you like.'))
        la.setWordWrap(True)
        l.addWidget(la)
        h = QHBoxLayout()
        cast = QVBoxLayout()
        chl = QLabel(_('&Play as:'))
        self.char_list = cw = QListWidget(cp)
        cw.setToolTip('<p>' + _('The characters you can play as. The one selected here is the one you will play.'))
        chl.setBuddy(cw)
        cw.currentRowChanged.connect(self.on_playable_character_changed)
        cast.addWidget(chl), cast.addWidget(cw)
        # The rest of the cast: characters the player will meet as the story
        # unfolds. They cannot be played as, but editing them shapes the world
        # the story is told in just as editing the playable characters does.
        self.npc_label = nl = QLabel(_('&Other characters in this world:'))
        self.npc_list = nw = QListWidget(cp)
        nw.setToolTip('<p>' + _('The other characters that live in this world. You will meet them as the story unfolds.'))
        nl.setBuddy(nw)
        nw.currentRowChanged.connect(self.on_npc_changed)
        cast.addWidget(nl), cast.addWidget(nw)
        h.addLayout(cast, stretch=1)
        self.character_editor = ce = CharacterEditor(cp)
        ce.portrait_refresh_requested.connect(self.regenerate_current_portrait)
        h.addWidget(ce, stretch=3)
        l.addLayout(h)

        h = QHBoxLayout()
        self.char_back_button = cbb = QPushButton(QIcon.ic('back.png'), _('&Back'), cp)
        cbb.setToolTip('<p>' + _('Go back and customize the world, or have the AI create a different cast of characters for it'))
        cbb.clicked.connect(self.show_world_page)
        h.addWidget(cbb)
        self.char_save_button = csb = QPushButton(QIcon.ic('save.png'), _('&Save world for later'), cp)
        csb.setToolTip('<p>' + _('Save this world so you can play more adventures in it later without re-generating it'))
        csb.clicked.connect(self.save_world)
        h.addWidget(csb)
        self.char_status_label = cst = QLabel('')
        cst.setWordWrap(True)
        h.addWidget(cst, stretch=10)
        self.start_button = pb = QPushButton(QIcon.ic('ok.png'), _('Start &playing'), cp)
        pb.clicked.connect(self.start_game)
        h.addWidget(pb)
        l.addLayout(h)
        s.addWidget(cp)

        self.portrait_result_received.connect(self.on_portrait_result, type=Qt.ConnectionType.QueuedConnection)

    def add_style_combo(self, h: QHBoxLayout, la: QLabel, styles: Sequence[ArtStyle | Pace | Tone | Narration], tooltip: str) -> QComboBox:
        c = style_combo(self, styles, tooltip)
        la.setBuddy(c)
        h.addWidget(la), h.addWidget(c)
        return c

    def load(
        self,
        brief: str,
        world: GeneratedWorld,
        style: StoryStyle = StoryStyle(),
        portraits: Sequence[dict[str, str] | None] = (),
        world_id: str = '',
        npc_portraits: Sequence[dict[str, str] | None] = (),
    ) -> None:
        self.brief = brief
        self.world_id = world_id
        self.images_enabled = data.images_enabled()
        self.cancel_portrait_generation()
        for name, key in style._asdict().items():
            combo = self.style_combos[name]
            combo.setCurrentIndex(max(0, combo.findData(key)))
        self.art_style_label.setVisible(self.images_enabled)
        self.art_style_combo.setVisible(self.images_enabled)
        self.character_editor.set_portrait_ui_visible(self.images_enabled)
        self.title_edit.setText(world.title)
        self.world_edit.load(world.world_description)
        self.load_cast(world, portraits, npc_portraits, style.art_style)
        self.stack.setCurrentWidget(self.world_page)

    def load_cast(
        self,
        world: GeneratedWorld,
        portraits: Sequence[dict[str, str] | None] = (),
        npc_portraits: Sequence[dict[str, str] | None] = (),
        portrait_style: str = '',
    ) -> None:
        # The cast of the world, with the portraits already generated for it,
        # if any: a world just generated has no cast at all and a world just
        # given one has no portraits yet.
        self.current_char_idx = -1
        self.characters = list(world.characters)
        self.npcs = list(world.npcs)
        self.cast_source = self.world_edit.markdown if self.characters else ''
        self.portraits = padded_portraits(portraits, len(self.characters)) + padded_portraits(npc_portraits, len(self.npcs))
        self.portrait_styles = [portrait_style if p else '' for p in self.portraits]
        for lw, names in ((self.char_list, [c.name for c in self.characters]), (self.npc_list, [c.name for c in self.npcs])):
            lw.blockSignals(True)  # the rows are loaded into the editor by show_character() below
            lw.clear()
            for name in names:
                lw.addItem(name)
            lw.setCurrentRow(0 if names else -1)
            lw.blockSignals(False)
        has_npcs = bool(self.npcs)
        self.npc_label.setVisible(has_npcs)
        self.npc_list.setVisible(has_npcs)
        self.update_next_button()
        self.show_character(0 if self.characters else -1)
        self.update_start_button()

    def update_next_button(self) -> None:
        # The button that leaves the world page either asks the AI for the
        # cast of the world or, when the world already has one, simply goes on
        # to it.
        nb = self.next_button
        if self.characters:
            nb.setIcon(QIcon.ic('forward.png'))
            nb.setText(_('Choose &character'))
            nb.setToolTip('<p>' + _('Proceed to the characters of this world and choose the one you will play as'))
        else:
            nb.setIcon(QIcon.ic('ai.png'))
            nb.setText(_('Create the &characters'))
            nb.setToolTip('<p>' + _('Have the AI create the characters that live in this world, based on the world description above'))

    def show_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.char_status_label.setText(text)

    def show_world_page(self) -> None:
        self.commit_character_edits()
        self.stack.setCurrentWidget(self.world_page)

    def proceed_to_characters(self) -> None:
        # Leaving the world page: have the AI create the cast for the world
        # that has just been described or edited, or, when the world already
        # has a cast that fits it, go straight on to it.
        if not self.title_edit.text().strip():
            return error_dialog(self, _('No title'), _('The world must have a title.'), show=True)
        if not self.world_edit.markdown:
            return error_dialog(self, _('No world description'), _('The world must have a description.'), show=True)
        if self.characters and self.world_edit.markdown == self.cast_source:
            self.show_character_page()
            return
        if self.characters and not question_dialog(
            self,
            _('Create new characters?'),
            _(
                'The description of this world has changed since its characters were created,'
                ' so they may no longer fit it. Have the AI create a new cast of characters for'
                ' the world as it is now? The existing characters and their portraits will be discarded.'
            ),
            yes_text=_('&Create new characters'),
            no_text=_('&Keep the existing ones'),
        ):
            self.cast_source = self.world_edit.markdown  # the player is happy with the cast as it is
            self.show_character_page()
            return
        self.cast_requested.emit(self.current_world)

    def show_character_page(self) -> None:
        self.stack.setCurrentWidget(self.character_page)
        self.generate_missing_portraits()

    def character_at(self, idx: int) -> PlayerCharacter | None:
        # The character at a combined index: the playable characters first,
        # then the non player characters, as a PlayerCharacter, which is all a
        # portrait needs. None when the index is not that of a character.
        if 0 <= idx < len(self.characters):
            return self.characters[idx]
        npc = self.npc_at(idx)
        return None if npc is None else PlayerCharacter(name=npc.name, description=npc.description, backstory=npc.backstory)

    def npc_at(self, idx: int) -> NonPlayerCharacter | None:
        i = idx - len(self.characters)
        return self.npcs[i] if 0 <= i < len(self.npcs) else None

    def list_and_row_for(self, idx: int) -> tuple[QListWidget, int]:
        # The list the character at a combined index is shown in and their row
        # in it, see character_at().
        if idx < len(self.characters):
            return self.char_list, idx
        return self.npc_list, idx - len(self.characters)

    def commit_character_edits(self) -> None:
        idx = self.current_char_idx
        c: PlayerCharacter | NonPlayerCharacter
        if 0 <= idx < len(self.characters):
            self.characters[idx] = c = self.character_editor.character
        elif self.npc_at(idx) is not None:
            self.npcs[idx - len(self.characters)] = c = self.character_editor.non_player_character
        else:
            return
        lw, row = self.list_and_row_for(idx)
        item = lw.item(row)
        if item is not None and c.name:
            item.setText(c.name)
        self.update_start_button()

    def on_playable_character_changed(self, row: int) -> None:
        self.show_character(row)
        self.update_start_button()

    def on_npc_changed(self, row: int) -> None:
        if row > -1:
            self.show_character(len(self.characters) + row)

    def show_character(self, idx: int) -> None:
        # Show the character at a combined index in the editor, saving the
        # edits made to the character shown before them.
        if idx == self.current_char_idx:
            return
        self.commit_character_edits()
        self.current_char_idx = idx
        if 0 <= idx < len(self.characters):
            self.character_editor.load(self.characters[idx])
            self.character_editor.set_story_fields_visible(False)
        elif (npc := self.npc_at(idx)) is not None:
            self.character_editor.load_npc(npc)
            # A character of a world that has no story yet has relationships
            # with the rest of the cast, but no current state.
            self.character_editor.set_story_fields_visible(True, current_state=False)
        self.update_portrait_display()

    def update_start_button(self) -> None:
        # Naming the character on the button makes it clear which of the two
        # lists of characters decides who the player plays as.
        row = self.char_list.currentRow()
        name = self.characters[row].name if -1 < row < len(self.characters) else ''
        self.start_button.setText(_('Start &playing as {}').format(name) if name else _('Start &playing'))

    # Character portrait generation {{{

    @property
    def style_combos(self) -> dict[str, QComboBox]:
        # The drop down that chooses each field of StoryStyle, keyed by the
        # name of the field.
        return {'art_style': self.art_style_combo, 'pace': self.pace_combo, 'tone': self.tone_combo, 'narration': self.narration_combo}

    @property
    def current_style(self) -> StoryStyle:
        return StoryStyle(
            art_style=str(self.art_style_combo.currentData() or ''),
            pace=str(self.pace_combo.currentData() or ''),
            tone=str(self.tone_combo.currentData() or ''),
            narration=str(self.narration_combo.currentData() or ''),
        )

    @property
    def current_art_style(self) -> str:
        return self.current_style.art_style

    def cancel_portrait_generation(self) -> None:
        # Any in-flight generation keeps running but its result is discarded
        # as its call number no longer matches.
        self.portrait_call = -1
        self.portrait_inflight = -1
        self.portrait_inflight_style = ''
        self.portrait_queue = []

    def generate_missing_portraits(self, force: Sequence[int] = ()) -> None:
        # Generate portraits for all characters that have none cached or
        # whose cached portrait was generated with a different art style.
        # Characters in force are re-generated unconditionally.
        if not self.images_enabled or not self.portraits:
            return
        style = self.current_art_style
        needed = [i for i in range(len(self.portraits)) if i in force or self.portraits[i] is None or self.portrait_styles[i] != style]
        needed.sort(key=lambda i: i != self.current_char_idx)  # the visible character first
        keep_inflight = self.portrait_inflight > -1 and self.portrait_inflight_style == style and self.portrait_inflight not in force
        if keep_inflight:
            self.portrait_queue = [i for i in needed if i != self.portrait_inflight]
        else:
            self.cancel_portrait_generation()
            self.portrait_queue = needed
            self.start_next_portrait()
        self.update_portrait_display()

    def regenerate_current_portrait(self) -> None:
        self.commit_character_edits()
        idx = self.current_char_idx
        if not self.images_enabled or not (-1 < idx < len(self.portraits)):
            return
        self.portraits[idx] = None
        self.portrait_styles[idx] = ''
        self.generate_missing_portraits(force=(idx,))

    def start_next_portrait(self) -> None:
        if not self.portrait_queue:
            return
        plugin = data.plugin_for('image')
        if plugin is None:
            self.cancel_portrait_generation()
            return
        while self.portrait_queue:
            idx = self.portrait_queue.pop(0)
            if (character := self.character_at(idx)) is not None:
                break
        else:
            return  # the queue held only characters that no longer exist
        style = self.current_art_style
        world_description = self.world_edit.markdown
        self.portrait_call = next(self.portrait_counter)
        self.portrait_inflight = idx
        self.portrait_inflight_style = style
        Thread(
            name='CYOAPortraitGen',
            daemon=True,
            target=self.do_generate_portrait,
            args=(character, idx, style, world_description, self.portrait_call, plugin),
        ).start()

    def do_generate_portrait(
        self, character: PlayerCharacter, idx: int, style: str, world_description: str, call_number: int, plugin: AIProviderPlugin
    ) -> None:
        try:
            pr = generate_portrait(character, style, world_description, plugin)
            if sip.isdeleted(self):
                return
            self.portrait_result_received.emit(call_number, idx, pr)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_portrait_result(self, call_number: int, idx: int, pr: PortraitResult) -> None:
        if call_number != self.portrait_call:
            return  # a stale result from a superseded or cancelled call
        self.portrait_call = -1
        self.portrait_inflight = -1
        self.portrait_inflight_style = ''
        if pr.error:
            name = c.name if (c := self.character_at(idx)) is not None else ''
            self.show_status(_('Failed to generate a portrait for {0}: {1}').format(name, pr.error))
            self.char_status_label.setToolTip(pr.error_details)
        elif idx < len(self.portraits):
            self.portraits[idx] = pr.portrait
            self.portrait_styles[idx] = pr.style
        self.start_next_portrait()
        self.update_portrait_display()

    def update_portrait_display(self) -> None:
        if not self.images_enabled:
            return
        idx = self.current_char_idx
        if idx > -1 and (idx == self.portrait_inflight or idx in self.portrait_queue):
            self.character_editor.show_portrait_busy(True)
            return
        self.character_editor.show_portrait_busy(False)
        p = self.portraits[idx] if -1 < idx < len(self.portraits) else None
        self.character_editor.set_portrait(standard_b64decode(p['data']) if p else None)

    # }}}

    @property
    def current_world(self) -> GeneratedWorld:
        self.commit_character_edits()
        return GeneratedWorld(
            title=self.title_edit.text().strip(),
            world_description=self.world_edit.markdown,
            characters=tuple(self.characters),
            npcs=tuple(self.npcs),
        )

    @property
    def playable_portraits(self) -> list[dict[str, str] | None]:
        return self.portraits[: len(self.characters)]

    @property
    def npc_portraits(self) -> list[dict[str, str] | None]:
        return self.portraits[len(self.characters) :]

    def save_world(self) -> None:
        w = self.current_world
        if not w.title:
            return error_dialog(self, _('No title'), _('The world must have a title to be saved.'), show=True)
        if not self.world_id:
            # A world saved for the first time under a title that is already
            # taken is assumed to be a re-generation of that world, so the
            # player is asked before it replaces it.
            idx = data.saved_world_index_with_title(w.title)
            if idx > -1:
                entry = data.saved_worlds()[idx]
                try:
                    existing = data.world_from_saved(entry)
                except Exception:
                    existing = None  # corrupted entry, offer to replace it
                if existing == w:
                    self.world_id = data.world_id_from_saved(entry)
                    self.show_status(_('World already saved.'))
                    return
                if not question_dialog(
                    self,
                    _('World already exists'),
                    _('A saved world named "{}" already exists. Replace it with this world?').format(w.title),
                ):
                    return
        self.world_id = data.add_saved_world(self.brief, w, self.current_style, self.playable_portraits, self.world_id, self.npc_portraits)
        self.show_status(_('World saved. You can select it when creating future adventures.'))

    def start_game(self) -> None:
        w = self.current_world
        row = self.char_list.currentRow()
        if not w.characters or not (-1 < row < len(w.characters)):
            return error_dialog(self, _('No character selected'), _('Select the character you will play as.'), show=True)
        if not w.characters[row].name:
            return error_dialog(self, _('No character name'), _('The character you play as must have a name.'), show=True)
        # A character with no name can neither be referred to by the AI nor be
        # matched with their entry in the story summary as the story changes
        # them, see calibre.ai.cyoa.updated_characters().
        for i, npc in enumerate(w.npcs):
            if not npc.name:
                self.npc_list.setCurrentRow(i)
                return error_dialog(self, _('No character name'), _('Every character of the world must have a name.'), show=True)
        self.start_requested.emit(w, row)


class CreateWorldWidget(QWidget):
    result_received = pyqtSignal(int, object)
    cast_result_received = pyqtSignal(int, object, object)  # (call_number, the GeneratedWorld the cast was created for, StructuredOutputResult)
    # (GeneratedWorld, index in its characters of the character to play as, brief, StoryStyle,
    #  the portraits of the characters of the world, keyed by character id)
    game_start_requested = pyqtSignal(object, int, str, object, object)
    saved_game_load_requested = pyqtSignal(str)  # the name of the saved game to resume instead of creating a new world

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
        left = QVBoxLayout()
        dl = QLabel(_('&Descriptions to generate a world from:'))
        self.descriptions_list = dli = QListWidget(bp)
        dl.setBuddy(dli)
        dli.currentItemChanged.connect(self.on_description_selected)
        left.addWidget(dl), left.addWidget(dli)
        self.saved_worlds_label = swl = QLabel(_('Previously created &worlds:'))
        self.saved_worlds_list = swli = QListWidget(bp)
        swl.setBuddy(swli)
        swli.currentItemChanged.connect(self.on_saved_world_selected)
        swli.itemActivated.connect(self.proceed_with_world)
        left.addWidget(swl), left.addWidget(swli)
        h.addLayout(left, stretch=1)

        self.right_stack = rs = QStackedLayout()

        self.generate_page = gp = QWidget(bp)
        v = QVBoxLayout(gp)
        v.setContentsMargins(0, 0, 0, 0)
        pl = QLabel(_('&World description:'))
        self.prompt_edit = pe = QPlainTextEdit(gp)
        pe.setPlaceholderText(_('Describe the world for your adventure'))
        pl.setBuddy(pe)
        v.addWidget(pl), v.addWidget(pe)
        bh = QHBoxLayout()
        self.generate_button = gb = QPushButton(QIcon.ic('ai.png'), _('&Generate world'), gp)
        gb.clicked.connect(self.start_generation)
        bh.addWidget(gb), bh.addStretch()
        v.addLayout(bh)
        rs.addWidget(gp)

        self.saved_world_page = sp = QWidget(bp)
        v = QVBoxLayout(sp)
        v.setContentsMargins(0, 0, 0, 0)
        self.saved_world_view = swv = TextDisplay(sp)
        swv.setOpenLinks(False)
        v.addWidget(swv)
        bh = QHBoxLayout()
        self.proceed_button = pb = QPushButton(QIcon.ic('ok.png'), _('&Proceed with world'), sp)
        pb.setToolTip('<p>' + _('Play in this world without re-generating it with AI'))
        pb.clicked.connect(self.proceed_with_world)
        bh.addWidget(pb)
        self.remove_button = rb = QPushButton(QIcon.ic('trash.png'), _('&Remove world'), sp)
        rb.setToolTip('<p>' + _('Delete this world from the list of saved worlds'))
        rb.clicked.connect(self.remove_world)
        bh.addWidget(rb), bh.addStretch()
        v.addLayout(bh)
        rs.addWidget(sp)

        h.addLayout(rs, stretch=2)
        bl.addLayout(h)
        lh = QHBoxLayout()
        self.load_game_button = lgb = QPushButton(QIcon.ic('document_open.png'), _('&Load saved game'), bp)
        lgb.setToolTip('<p>' + _('Resume a game you saved earlier instead of starting a new one in a new world'))
        lgb.clicked.connect(self.load_saved_game)
        lh.addWidget(lgb), lh.addStretch()
        bl.addLayout(lh)
        self.populate_descriptions_list()
        self.populate_saved_worlds_list()
        self.update_load_game_button()

        self.wait_stack = ws = WaitStack(WORLD_GENERATION_MESSAGE, after=bp, parent=self, size=128)
        ws.stop()
        s.addWidget(ws)

        self.world_edit = we = WorldEditWidget(self)
        we.start_requested.connect(self.on_start_requested)
        we.back_requested.connect(self.show_brief_page)
        we.cast_requested.connect(self.generate_cast_for_world)
        s.addWidget(we)

        self.result_received.connect(self.on_result, type=Qt.ConnectionType.QueuedConnection)
        self.cast_result_received.connect(self.on_cast_result, type=Qt.ConnectionType.QueuedConnection)

    def populate_descriptions_list(self) -> None:
        self.descriptions_list.clear()
        for pw in PREMADE_WORLDS:
            i = QListWidgetItem(pw.title, self.descriptions_list)
            i.setData(BRIEF_ROLE, pw.brief)

    def populate_saved_worlds_list(self) -> None:
        self.saved_worlds_list.clear()
        saved = data.saved_worlds()
        for idx, entry in enumerate(saved):
            title = (entry.get('world') or {}).get('title') or _('Untitled world')
            i = QListWidgetItem(title, self.saved_worlds_list)
            i.setToolTip('<p>' + _('A world you created previously. Select it to play in it without re-generating it.'))
            i.setData(SAVED_WORLD_ROLE, idx)
        has_saved = bool(saved)
        self.saved_worlds_label.setVisible(has_saved)
        self.saved_worlds_list.setVisible(has_saved)

    def update_load_game_button(self) -> None:
        # With no saved games there is nothing for the dialog to show, so the
        # button would be a dead end.
        self.load_game_button.setVisible(has_saved_games())

    def load_saved_game(self) -> None:
        d = LoadGameDialog(self)
        if d.exec() == Dialog.DialogCode.Accepted and d.save_name:
            self.saved_game_load_requested.emit(d.save_name)

    def saved_world_for_item(self, item: QListWidgetItem) -> tuple[dict[str, object], GeneratedWorld] | None:
        idx = item.data(SAVED_WORLD_ROLE)
        try:
            entry = data.saved_worlds()[idx]
            world = data.world_from_saved(entry)
        except Exception as e:
            error_dialog(self, _('Corrupted saved world'), _('Failed to load the saved world: {}').format(e), show=True)
            return None
        return entry, world

    def on_description_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.saved_worlds_list.setCurrentItem(None)
        if brief := current.data(BRIEF_ROLE):
            self.prompt_edit.setPlainText(brief)
        self.right_stack.setCurrentWidget(self.generate_page)

    def on_saved_world_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self.descriptions_list.setCurrentItem(None)
        sw = self.saved_world_for_item(current)
        if sw is None:
            return
        world = sw[1]
        md = [f'# {world.title}', '', world.world_description, '']
        if world.characters:
            md.extend(('## ' + _('Characters you can play as'), ''))
            for c in world.characters:
                md.extend((f'### {c.name}', '', c.description, '', c.backstory, ''))
        if world.npcs:
            md.extend(('## ' + _('Other characters in this world'), ''))
            for npc in world.npcs:
                md.extend((f'### {npc.name}', '', npc.description, '', npc.backstory, ''))
        self.saved_world_view.setMarkdown('\n'.join(md))
        self.right_stack.setCurrentWidget(self.saved_world_page)

    def proceed_with_world(self) -> None:
        item = self.saved_worlds_list.currentItem()
        if item is None:
            return
        sw = self.saved_world_for_item(item)
        if sw is None:
            return
        entry, world = sw
        self.current_brief = str(entry.get('brief') or '')
        self.world_edit.load(
            self.current_brief,
            world,
            data.style_from_saved(entry),
            data.portraits_from_saved(entry, len(world.characters)),
            data.world_id_from_saved(entry),
            data.npc_portraits_from_saved(entry, len(world.npcs)),
        )
        self.world_edit.show_status('')
        self.stack.setCurrentWidget(self.world_edit)

    def remove_world(self) -> None:
        item = self.saved_worlds_list.currentItem()
        if item is None:
            return
        if not question_dialog(self, _('Are you sure?'), _('Permanently remove the saved world "{}"? This cannot be undone.').format(item.text())):
            return
        idx = item.data(SAVED_WORLD_ROLE)
        try:
            data.remove_saved_world(idx)
        except IndexError:
            pass
        self.populate_saved_worlds_list()
        self.right_stack.setCurrentWidget(self.generate_page)

    def show_brief_page(self) -> None:
        self.current_call_number = -1  # cancels any in-flight generation
        self.world_edit.cancel_portrait_generation()
        self.wait_stack.stop()
        self.populate_saved_worlds_list()
        self.update_load_game_button()
        self.right_stack.setCurrentWidget(self.generate_page)
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
        self.wait_stack.msg = WORLD_GENERATION_MESSAGE
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
        if not isinstance(world, GeneratedWorld):
            error_dialog(self, _('World generation failed'), _('The AI returned an invalid world, try again.'), det_msg=res.raw, show=True)
            return
        # The characters are created only once the player is happy with the
        # world, see generate_cast_for_world().
        self.world_edit.load(self.current_brief, world, recommended_style(self.current_brief))
        self.world_edit.show_status(generation_status(res))
        self.stack.setCurrentWidget(self.world_edit)

    def generate_cast_for_world(self, world: GeneratedWorld) -> None:
        # The second half of world creation: the cast is created from the
        # world as the player edited it, so that the characters fit the world
        # that will actually be played in.
        plugin = data.plugin_for('text')
        if plugin is None:
            error_dialog(self, _('No AI configured'), _('No AI for text generation has been configured for the game.'), show=True)
            return
        self.current_call_number = next(self.counter)
        self.wait_stack.msg = _('Creating the characters of your world, this can take a while…')
        self.wait_stack.start()
        self.stack.setCurrentWidget(self.wait_stack)
        Thread(name='CYOACastGen', daemon=True, target=self.do_generate_cast, args=(world, self.current_call_number, plugin)).start()

    def do_generate_cast(self, world: GeneratedWorld, call_number: int, plugin: AIProviderPlugin) -> None:
        try:
            # the preferences overlay is thread local so must be entered here
            with data.cyoa_ai_settings():
                res = generate_cast(self.current_brief, world, plugin)
            if sip.isdeleted(self):
                return
            self.cast_result_received.emit(call_number, world, res)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_cast_result(self, call_number: int, world: GeneratedWorld, res: StructuredOutputResult) -> None:
        if call_number != self.current_call_number:
            return  # a stale result from a superseded or cancelled call
        self.wait_stack.stop()
        self.wait_stack.msg = WORLD_GENERATION_MESSAGE
        # However the cast turns out, the player goes back to the world they
        # asked for characters for, rather than to the start of the flow.
        self.stack.setCurrentWidget(self.world_edit)
        if res.exception is not None:
            error_dialog(
                self, _('Character creation failed'), _('Failed to create the characters: {}').format(res.exception), det_msg=res.error_details, show=True
            )
            return
        cast = res.data
        if not isinstance(cast, GeneratedCast) or not cast.characters:
            error_dialog(self, _('Character creation failed'), _('The AI returned no usable characters, try again.'), det_msg=res.raw, show=True)
            return
        # The portraits of the previous cast, if any, are of characters that
        # no longer exist, so load_cast() starts with none.
        self.world_edit.load_cast(world._replace(characters=cast.characters, npcs=cast.npcs))
        self.world_edit.show_status(generation_status(res))
        self.world_edit.show_character_page()

    def on_start_requested(self, world: GeneratedWorld, character_index: int) -> None:
        # Remember the world so more adventures can be played in it later. The
        # saved world is only the template the game starts from: the portraits
        # of the characters the game starts with are handed to it, and it
        # stores its own copies of them from then on.
        we = self.world_edit
        playable, npcs = we.playable_portraits, we.npc_portraits
        we.world_id = data.add_saved_world(we.brief, world, we.current_style, playable, we.world_id, npcs)
        portraits: dict[str, dict[str, str]] = {}
        if (p := playable[character_index] if -1 < character_index < len(playable) else None) is not None:
            portraits[PROTAGONIST_ID] = p
        # The non player characters keep the ids they are given in the story
        # summary of the game, which is what their portraits are stored under.
        for cid, p in zip(npc_character_ids(world.npcs), npcs):
            if p is not None:
                portraits[cid] = p
        self.game_start_requested.emit(world, character_index, we.brief, we.current_style, portraits)


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    w = CreateWorldWidget()
    w.game_start_requested.connect(
        lambda world, character_index, brief, style, portraits: print('start playing:', world.title, 'as', world.characters[character_index].name)
    )
    w.resize(900, 600)
    w.show()
    app.exec()
    del w
    del app
