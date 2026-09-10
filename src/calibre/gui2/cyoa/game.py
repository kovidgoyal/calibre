#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The gameplay widget of the "Create Your Own Adventure" game. The story of
# the current chapter is shown turn-by-turn in a text browser with a prompt
# box below it to enter the action to take. A picture of the scene currently
# scrolled into view is shown on the right, when an image AI is configured.
# The game is auto-saved after every turn; the toolbar allows saving under a
# name of the player's choosing, loading such saves, rewinding, editing the
# world (its characters and the story memory the AI is given) and starting
# over in a new world, while a checkbox in the scene panel turns scene
# images on/off.

from bisect import bisect_right
from collections.abc import Callable
from functools import partial
from html import escape
from itertools import count
from threading import Thread
from time import monotonic
from typing import NamedTuple

from qt.core import (
    QAction,
    QCheckBox,
    QCursor,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QIcon,
    QImage,
    QInputDialog,
    QKeySequence,
    QLabel,
    QMenu,
    QMimeData,
    QPixmap,
    QPoint,
    QPushButton,
    QShortcut,
    QShowEvent,
    QSpinBox,
    QSplitter,
    QStatusBar,
    Qt,
    QTextBlockFormat,
    QTextBrowser,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextEdit,
    QTimer,
    QToolBar,
    QToolTip,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.ai import ImageGenerationOptions, StructuredOutputResult
from calibre.ai.cyoa import (
    PROTAGONIST_ID,
    AIProvider,
    GameState,
    PlayerCharacter,
    QuickAction,
    deserialize_game,
    next_turn,
    quick_action_kind_name,
    rewind,
    scene_image_prompt,
    serialize_game,
)
from calibre.ai.utils import ContentType, response_to_html
from calibre.customize import AIProviderPlugin
from calibre.gui2 import config, error_dialog, qapplication_or_fail, question_dialog, safe_open_url
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.saves import LoadGameDialog, SaveGameDialog
from calibre.gui2.cyoa.settings import ConfigureImageAIDialog, SettingsDialog
from calibre.gui2.cyoa.story_widgets import PromptEdit, SceneImageDisplay, StoryView
from calibre.gui2.cyoa.text_display import TextDisplay
from calibre.gui2.cyoa.world_editor import EditWorldDialog
from calibre.gui2.image_popup import ImagePopup
from calibre.gui2.progress_indicator import WaitStack
from calibre.gui2.widgets2 import Dialog
from calibre.utils.img import image_from_data, image_to_data, resize_to_fit
from calibre.utils.localization import _, ngettext
from calibre.utils.resources import get_image_path

QUICK_ACTION_SCHEME = 'quick-action'
# Quick action number i is activated by pressing Ctrl+(i+1)
MAX_QUICK_ACTION_SHORTCUTS = 9
# Scene images are stored downscaled to fit this many pixels in either
# dimension, keeping saved games reasonably small.
SCENE_IMAGE_SIZE = 1280
# The ornamental divider drawn between turns, rendered from
# imgsrc/scene-divider.svg at twice its display width so it stays crisp on
# high DPI screens.
SCENE_DIVIDER_URL = 'cyoa://scene-divider'
SCENE_DIVIDER_WIDTH = 300  # display width in the story view in device independent pixels
INFO_DIVIDER_WIDTH = 220  # a narrower divider for the info panel, so it does not need to scroll horizontally
# Symbols for the currencies AI providers commonly bill in.
CURRENCY_SYMBOLS = {'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥', 'INR': '₹', 'KRW': '₩'}


def fmt_cost(cost: float, currency: str) -> str:
    # At most four decimal places so fractions of a cent stay visible, at
    # least two so amounts look like money, e.g. 0.0123 -> $0.0123 and
    # 0.5 -> $0.50 for USD.
    amount = f'{cost:.4f}'.rstrip('0')
    if len(amount) - 1 - amount.index('.') < 2:
        amount = f'{cost:.2f}'
    if symbol := CURRENCY_SYMBOLS.get(currency.upper()):
        return symbol + amount
    return f'{amount} {currency}'.strip()


def insert_scene_divider(c: QTextCursor) -> None:
    # The divider needs its own insertion helper as insertHtml() merges the
    # fragment's first block into the current block, losing the center
    # alignment, see insert_html_block().
    bf = QTextBlockFormat()
    bf.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    bf.setTopMargin(12), bf.setBottomMargin(12)
    c.insertBlock(bf, QTextCharFormat())
    c.insertHtml(f'<img src="{SCENE_DIVIDER_URL}">')


def insert_html_block(c: QTextCursor, html: str) -> None:
    # QTextCursor.insertHtml() merges the first block of the fragment into
    # the current block, which inherits its block format. Sequential calls
    # thus run text into the preceding heading and attach the ruler of a
    # preceding <hr> to the following paragraph, so start every fragment in
    # a fresh block with default formatting.
    if c.position():
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
    c.insertHtml(html)


def quick_action_kind_html(action: QuickAction) -> str:
    # The kind of approach an action takes, shown after it in a discreet
    # italic aside. Empty for the catch-all kind, which is not worth the
    # space, see quick_action_kind_name().
    if kind := quick_action_kind_name(action.kind):
        return f' <i>&mdash; {escape(kind)}</i>'
    return ''


def quick_action_as_text(action: QuickAction) -> str:
    # An action and its kind as plain text, for the clipboard.
    if kind := quick_action_kind_name(action.kind):
        return f'{action.text} — {kind}'
    return action.text


class SceneImageResult(NamedTuple):
    # The outcome of generating the picture of one turn's scene.
    image: data.SceneImage | None
    error: str = ''
    error_details: str = ''


class GameWidget(QWidget):
    game_abandoned = pyqtSignal()

    turn_result_received = pyqtSignal(int, object, object)  # (call_number, GameState the turn was played on, StructuredOutputResult)
    turn_narrative_received = pyqtSignal(int, str)  # (call_number, the next fragment of the prose of the turn being written)
    image_result_received = pyqtSignal(int, int, object)  # (call_number, turn number, SceneImageResult)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game_id = ''
        self.state: GameState | None = None
        self.images: dict[int, data.SceneImage] = {}  # keyed by one based turn number
        # One based numbers of the turns whose scene image generation failed,
        # shown a retry button in the scene panel. Not saved with the game.
        self.failed_image_turns: set[int] = set()
        # Portraits of the characters of this game, keyed by the stable id of
        # the character they depict, saved as part of the game.
        self.portraits: dict[str, dict[str, str]] = {}
        self.images_enabled = False
        self.session_cost = 0.0
        self.last_save_name = ''
        # Turn and image generation run one at a time on background threads:
        # turn_call/image_call identify the current generation, results from
        # superseded calls are discarded. image_turn is the turn number whose
        # scene image is being generated. Turns are played on a copy of the
        # game state which is adopted when the result arrives, so that
        # rewinding while a turn is in-flight cannot corrupt the game.
        self.turn_counter = count(start=1)
        self.turn_call = -1
        # What the in-flight turn generation was asked for, so that it can be
        # retried if the turn times out or fails.
        self.turn_request: tuple[str, bool] | None = None
        # Set while the dialog asking what to do about a turn that has taken
        # too long is open. The turn is still in flight, so a result that
        # arrives during that dialog's nested event loop is stashed in
        # late_turn_result and applied when the dialog closes, rather than
        # being applied behind the dialog or, worse, thrown away.
        self.turn_timed_out = False
        self.turn_timeout_dialog: QDialog | None = None
        self.late_turn_result: tuple[int, GameState, StructuredOutputResult] | None = None
        self.turn_timer = QTimer(self)
        self.turn_timer.setSingleShot(True)
        self.turn_timer.timeout.connect(self.on_turn_timeout)
        self._thinking_start: float = 0.0
        self._thinking_ticker = QTimer(self)
        self._thinking_ticker.setInterval(1000)
        self._thinking_ticker.timeout.connect(self._update_thinking_elapsed)
        # The prose of the turn being generated, as far as the AI has written
        # it, shown in the story view while the rest of the turn is generated,
        # see render_story(). The fragments arrive many times a second, so
        # the display is refreshed by a timer rather than for every fragment.
        self.streamed_narrative = ''
        # Where in the story document the prose of the turn being generated is
        # rendered, -1 when no turn is being generated.
        self.streaming_block_start = -1
        self.narrative_render_timer = t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(100)
        t.timeout.connect(self.render_streamed_narrative)
        self.image_counter = count(start=1)
        self.image_call = -1
        self.image_turn = -1
        # Scrolling the story view emits valueChanged continuously, in
        # particular under momentum scrolling, and working out which turn is
        # on screen needs layout queries, so the scene panel is only
        # refreshed once the scrolling has paused, see on_story_scrolled().
        self.scroll_settle_timer = t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(50)
        t.timeout.connect(self.update_scene_panel)
        # (document position, one based turn number) of every turn shown in
        # the story view, used to map the scroll position to a turn.
        self.turn_positions: list[tuple[int, int]] = []
        # The turn to scroll to once the widget is shown, see scroll_to_turn()
        self.pending_scroll_turn = 0
        # Substituted by tests and the demo in __main__ to play without AI
        self.plugin_override: AIProvider | None = None

        l = QVBoxLayout(self)
        self.toolbar = tb = QToolBar(self)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        def toolbar_action(icon: str, text: str, tooltip: str, receiver: Callable[[], None]) -> QAction:
            a = QAction(QIcon.ic(icon), text, self)
            a.setToolTip(tooltip)
            a.triggered.connect(receiver)
            tb.addAction(a)
            return a

        self.save_action = toolbar_action('save.png', _('Save'), _('Save this game under a name of your choosing'), self.save_game_as)
        self.load_action = toolbar_action('document_open.png', _('Load'), _('Load a previously saved game, replacing the current game'), self.load_saved_game)
        self.restart_action = toolbar_action('restart.png', _('Restart'), _('Restart the adventure from the first turn'), self.restart_game)
        self.back_action = toolbar_action(
            'edit-undo.png',
            _('Back to turn'),
            _('Go back to an earlier turn, discarding all turns after it. Press {} to go back one turn').format('Alt+Left'),
            self.back_to_turn,
        )
        self.world_action = toolbar_action(
            'metadata.png',
            _('Edit world'),
            _('View and edit the characters of the story and their portraits, and the story memory the AI continues the story from'),
            self.edit_world,
        )
        self.settings_action = toolbar_action(
            'config.png', _('Settings'), _('Change the AIs used to generate the story and the pictures of each scene'), self.change_settings
        )
        self.exit_action = toolbar_action(
            'back.png', _('New world'), _('Leave this game and return to the world creation screen'), self.exit_to_world_generation
        )
        l.addWidget(tb)

        self.splitter = sp = QSplitter(self)
        sp.setChildrenCollapsible(False)
        self.splitter_state_restored = False
        sp.splitterMoved.connect(self.save_splitter_state, type=Qt.ConnectionType.QueuedConnection)
        left = QWidget(sp)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.story_view = sv = StoryView(left)
        sv.setOpenLinks(False)
        sv.anchorClicked.connect(self.on_link_clicked)
        sv.highlighted.connect(self.on_link_hovered)
        vsb = sv.verticalScrollBar()
        if vsb is not None:
            vsb.valueChanged.connect(self.on_story_scrolled)
        ll.addWidget(sv, stretch=10)

        input_panel = QWidget(left)
        il = QVBoxLayout(input_panel)
        il.setContentsMargins(0, 0, 0, 0)
        self.prompt_edit = pe = PromptEdit(input_panel)
        pe.setPlaceholderText(_('What do you do next?'))
        pe.submit_requested.connect(self.take_action)
        il.addWidget(pe)
        h = QHBoxLayout()
        self.action_button = ab = QPushButton(QIcon.ic('ok.png'), _('Take &action'), input_panel)
        ab.setToolTip('<p>' + _('Submit your action to the AI. You can also press {} in the box above').format('Ctrl+Enter'))
        ab.clicked.connect(self.take_action)
        h.addWidget(ab)
        self.interesting_button = ib = QPushButton(QIcon.ic('ai.png'), _('Something &interesting happens'), input_panel)
        ib.setToolTip('<p>' + _('Instead of taking an action yourself, have the AI make something unexpected and interesting happen next'))
        ib.clicked.connect(self.interesting_event)
        h.addWidget(ib), h.addStretch()
        il.addLayout(h)
        self.input_stack = ws = WaitStack(_('Thinking…'), after=input_panel, parent=left, size=64)
        # A discreet Stop button in the corner of the overlay, for abandoning
        # a turn that is taking too long or was asked for by mistake.
        ws.enable_corner_button('window-close.png', '<p>' + _('Stop waiting for the AI to write this turn. The AI provider may still charge for it.'))
        ws.corner_button_clicked.connect(self.stop_turn)
        ws.stop()
        ll.addWidget(ws)
        sp.addWidget(left)

        right = QWidget(sp)
        self.right_panel_layout = rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.scene_image = si = SceneImageDisplay(right)
        si.popup_requested.connect(self.show_scene_image_popup)
        si.context_menu_requested.connect(self.show_scene_image_context_menu)
        si.refresh_requested.connect(self.regenerate_scene_image)
        rl.addWidget(si)
        self.scene_filler = filler = QWidget(right)  # absorbs the leftover space under the scene image when images are shown
        rl.addWidget(filler, stretch=10)
        self.info_view = iv = TextDisplay(right)  # shown instead of the image when the image AI is disabled
        rl.addWidget(iv, stretch=10)
        self.images_check = ic = QCheckBox(_('&Generate images'), right)
        ic.setToolTip('<p>' + _('Show AI generated pictures of each scene. When turned off, no images are generated for new turns'))
        ic.clicked.connect(self.toggle_images)  # clicked, not toggled, so programmatic setChecked() does not re-enter
        rl.addWidget(ic)
        sp.addWidget(right)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 1)
        l.addWidget(sp, stretch=10)

        self.status_bar = sb = QStatusBar(self)
        sb.setSizeGripEnabled(False)
        self.status_label = sl = QLabel(sb)
        sb.addPermanentWidget(sl)
        l.addWidget(sb)

        # The ornamental divider drawn between turns, pre-scaled for this
        # screen. It must be re-registered on the story document after every
        # clear(), as that discards document resources.
        dpr = self.devicePixelRatioF()
        src = QImage(get_image_path('scene-divider.png'))

        def scaled_divider(width: int) -> QImage:
            img = src.scaledToWidth(round(width * dpr), Qt.TransformationMode.SmoothTransformation)
            img.setDevicePixelRatio(dpr)
            return img

        self.scene_divider = scaled_divider(SCENE_DIVIDER_WIDTH)
        self.add_scene_divider_resource(iv, scaled_divider(INFO_DIVIDER_WIDTH))

        self.image_popup = ImagePopup(self)
        self.copy_image_action = a = QAction(QIcon.ic('edit-copy.png'), _('&Copy image to clipboard'), self)
        a.setShortcut(QKeySequence('Ctrl+Alt+C', QKeySequence.SequenceFormat.PortableText))
        a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        a.triggered.connect(self.copy_scene_image)
        self.addAction(a)
        self.popup_image_action = a = QAction(QIcon.ic('view-image.png'), _('&Show image in a popup window'), self)
        a.triggered.connect(self.show_scene_image_popup)
        self.edit_image_prompt_action = a = QAction(QIcon.ic('edit_input.png'), _('&Edit prompt and regenerate image'), self)
        a.triggered.connect(self.edit_scene_image_prompt)
        self.copy_turn_action = a = QAction(QIcon.ic('edit-copy.png'), _('Copy current &turn to clipboard'), self)
        a.setShortcut(QKeySequence('Ctrl+Shift+C', QKeySequence.SequenceFormat.PortableText))
        a.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        a.triggered.connect(self.copy_current_turn)
        self.addAction(a)
        sv.copy_turn_action = a

        # Ctrl+1, Ctrl+2, … activate the corresponding quick action link
        for i in range(MAX_QUICK_ACTION_SHORTCUTS):
            sc = QShortcut(QKeySequence(f'Ctrl+{i + 1}'), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(partial(self.activate_quick_action, i))
        # Alt+Left goes back one turn, after a confirmation
        sc = QShortcut(QKeySequence('Alt+Left'), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self.go_back)

        # Focus given to this widget, e.g. when it becomes the visible page
        # of the main window, goes to the box the player types into.
        self.setFocusProxy(self.prompt_edit)

        self.turn_result_received.connect(self.on_turn_result, type=Qt.ConnectionType.QueuedConnection)
        self.turn_narrative_received.connect(self.on_turn_narrative, type=Qt.ConnectionType.QueuedConnection)
        self.image_result_received.connect(self.on_image_result, type=Qt.ConnectionType.QueuedConnection)

    def showEvent(self, a0: QShowEvent | None) -> None:
        super().showEvent(a0)
        if not self.splitter_state_restored:
            self.splitter_state_restored = True
            if state := data.game_splitter_state():
                self.splitter.restoreState(state)
            else:
                # With no saved state, make the scene panel wide enough to
                # show a 4:3 scene image using most of the panel height
                # (leaving room for the condition text under it), while
                # keeping the majority of the width for the story.
                total = self.splitter.width()
                image_height = int(self.splitter.height() * 0.75)
                image_width = max(250, min(int(image_height * 4 / 3), int(total * 0.45)))
                self.splitter.setSizes([total - image_width, image_width])
        if self.pending_scroll_turn:
            # The story was rendered while the widget was hidden, with the
            # document laid out for the wrong geometry, so scroll only now,
            # once this show and the splitter sizing above have taken effect.
            tn, self.pending_scroll_turn = self.pending_scroll_turn, 0
            QTimer.singleShot(0, partial(self.scroll_to_turn, tn))

    def save_splitter_state(self) -> None:
        if self.splitter_state_restored:  # ignore programmatic moves during initial layout
            data.save_game_splitter_state(bytes(self.splitter.saveState()))

    def load_game(
        self, game_id: str, state: GameState, images: dict[int, data.SceneImage] | None = None, portraits: dict[str, dict[str, str]] | None = None
    ) -> None:
        self.game_id = game_id
        self.state = state
        self.images = dict(images or {})
        self.failed_image_turns = set()
        self.portraits = dict(portraits or {})
        self.images_enabled = data.images_enabled()
        self.session_cost = 0.0
        self.last_save_name = data.save_name_for_title(state.world.title)
        self.cancel_pending_ai_calls()
        self.images_check.setChecked(self.images_enabled)
        self.apply_images_enabled()
        self.prompt_edit.clear()
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.refresh_ui()
        if not state.turns:
            self.request_turn('')  # the opening turn of a new game
        elif self.images_enabled and len(state.turns) not in self.images:
            self.request_image(len(state.turns))

    def _update_thinking_elapsed(self) -> None:
        secs = int(monotonic() - self._thinking_start)
        if secs < 60:
            human = ngettext('{} second', '{} seconds', secs).format(secs)
        else:
            mins, s = divmod(secs, 60)
            human = _('{m}m {s}s').format(m=mins, s=s)
        # Once prose starts arriving the AI is no longer thinking but writing
        self.input_stack.msg = (_('Writing… {}') if self.streamed_narrative else _('Thinking… {}')).format(human)

    def _stop_thinking(self) -> None:
        self._thinking_ticker.stop()
        self.input_stack.stop()

    def abandon_pending_turn(self) -> None:
        # Stop waiting for the turn being generated. It keeps running, as
        # there is no way to abort a request to an AI provider, but its result
        # is discarded when it arrives as its call number no longer matches.
        self.turn_call = -1
        self.turn_request = None
        self.turn_timed_out = False
        self.late_turn_result = None
        self.turn_timer.stop()
        self._stop_thinking()
        self.discard_pending_turn_display()

    def discard_pending_turn_display(self) -> None:
        # Remove the prose of a turn that was being written from the story
        # view, once the turn has been given up on or has failed. Must be
        # called after turn_call has been reset, so that render_story() does
        # not put the prose right back.
        self.streamed_narrative = ''
        self.narrative_render_timer.stop()
        if self.streaming_block_start > -1:
            self.render_story()
            if self.state is not None and self.state.turns:
                self.scroll_to_turn(len(self.state.turns))

    def cancel_pending_ai_calls(self) -> None:
        # In-flight generations keep running but their results are discarded
        # as their call numbers no longer match.
        self.abandon_pending_turn()
        self.image_call = -1
        self.image_turn = -1

    def stop_turn(self) -> None:
        # The Stop button of the "Thinking…" overlay. The game is left exactly
        # as it was before the turn was asked for, so the player can edit
        # their action and try again, or do something else entirely.
        if self.turn_call < 0:
            return
        self.abandon_pending_turn()
        self.status_bar.showMessage(_('Stopped waiting for this turn. The AI provider may still charge for it.'), 5000)
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh_text_display(self) -> None:
        # The colors of the links of the story are baked into the document
        # when the HTML is parsed, so the story and the info panel have to be
        # rendered again for a change to the text display settings to become
        # fully visible, without losing the place the player is reading at.
        tn = self.visible_turn_number()
        self.render_story()
        self.info_view.setProperty('cyoa-html', None)
        self.update_scene_panel()
        if tn:
            self.scroll_to_turn(tn)

    def refresh_ui(self) -> None:
        self.render_story()
        if self.state is not None and self.state.turns:
            self.scroll_to_turn(len(self.state.turns))
        self.update_window_title()
        self.update_status()
        self.update_scene_panel()

    # Story display {{{

    def add_scene_divider_resource(self, view: QTextBrowser, divider: QImage | None = None) -> None:
        doc = view.document()
        if doc is not None:
            doc.addResource(int(QTextDocument.ResourceType.ImageResource), QUrl(SCENE_DIVIDER_URL), divider if divider is not None else self.scene_divider)

    def render_story(self) -> None:
        sv = self.story_view
        sv.clear()
        self.add_scene_divider_resource(sv)  # clear() discards document resources
        sv.apply_max_line_width()  # as does the margin limiting the line length
        self.turn_positions = []
        state = self.state
        if state is None:
            return
        c = sv.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        if not state.turns:
            insert_html_block(c, f'<h2>{escape(state.world.title)}</h2>')
            insert_html_block(c, response_to_html(state.world.world_description, ContentType.markdown))
        else:
            insert_html_block(c, f'<h2>{escape(state.chapter_titles[state.current_chapter])}</h2>')
            for i, t in enumerate(state.turns):
                if t.chapter != state.current_chapter:
                    continue
                if self.turn_positions:
                    insert_scene_divider(c)
                self.turn_positions.append((c.position(), i + 1))
                if t.player_input:
                    insert_html_block(c, f'<p><i>➤ {escape(t.player_input)}</i></p>')
                insert_html_block(c, response_to_html(t.turn.narrative, ContentType.markdown))
        if self.turn_call > -1 and self.turn_request is not None:
            # A turn is being generated: show the action the player took and
            # the prose the AI has written so far in place of the quick
            # actions, which are for a turn that has already been played.
            insert_scene_divider(c)
            player_input = self.turn_request[0]  # empty for the opening turn and for "something interesting happens"
            if player_input:
                insert_html_block(c, f'<p><i>➤ {escape(player_input)}</i></p>')
            self.streaming_block_start = c.position()
            if self.streamed_narrative:
                insert_html_block(c, response_to_html(self.streamed_narrative, ContentType.markdown))
            return
        self.streaming_block_start = -1
        if not state.turns:
            return
        insert_scene_divider(c)
        last = state.turns[-1].turn
        if last.quick_actions:
            # each action in its own paragraph with a top margin, giving
            # enough space between the links to click them comfortably, with
            # the kind of approach it takes after it, so that the three read
            # as the three different choices they are meant to be
            items = ''.join(
                f'<p style="margin-top: 8px; margin-left: 16px"><a href="{QUICK_ACTION_SCHEME}:{i}">{escape(a.text)}</a>{quick_action_kind_html(a)}</p>'
                for i, a in enumerate(last.quick_actions)
            )
            insert_html_block(c, f'<h4>{_("Quick actions")}</h4>' + items)

    def render_streamed_narrative(self) -> None:
        # Replace the prose of the turn being generated in the story view
        # with what the AI has written so far. The prose is Markdown, which
        # cannot be rendered a fragment at a time, so the whole passage is
        # rendered again, which is cheap as it is at most a few thousand
        # characters and happens at most ten times a second.
        if self.streaming_block_start < 0 or self.turn_call < 0:
            return
        sv = self.story_view
        doc = sv.document()
        if doc is None or self.streaming_block_start > doc.characterCount():
            return  # the document was replaced under us, render_story() will restore the prose
        vsb = sv.verticalScrollBar()
        # Follow the prose as it is written unless the player has scrolled
        # away from the end to re-read something.
        follow = vsb is None or vsb.value() >= vsb.maximum() - 4
        c = sv.textCursor()
        c.beginEditBlock()
        c.setPosition(self.streaming_block_start)
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()
        if self.streamed_narrative:
            insert_html_block(c, response_to_html(self.streamed_narrative, ContentType.markdown))
        c.endEditBlock()
        if follow and vsb is not None:
            vsb.setValue(vsb.maximum())

    def quick_action(self, action_number: int) -> QuickAction | None:
        # The zero based action_number quick action of the last turn, None
        # when there is no such action.
        if self.state is None or not self.state.turns:
            return None
        actions = self.state.turns[-1].turn.quick_actions
        return actions[action_number] if 0 <= action_number < len(actions) else None

    def activate_quick_action(self, action_number: int) -> None:
        # Put the quick action into the prompt box, submitting it when it is
        # already there, so that activating an action twice plays it.
        a = self.quick_action(action_number)
        if a is None:
            return
        action = a.text
        if self.prompt_edit.toPlainText().strip() == action:
            self.take_action()
            return
        self.prompt_edit.setPlainText(action)
        self.prompt_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def on_link_clicked(self, url: QUrl) -> None:
        if url.scheme() != QUICK_ACTION_SCHEME:
            safe_open_url(url)
            return
        try:
            action_number = int(url.path())
        except ValueError:
            return
        self.activate_quick_action(action_number)

    def on_link_hovered(self, url: QUrl) -> None:
        if url.scheme() != QUICK_ACTION_SCHEME:
            QToolTip.hideText()
            return
        try:
            action_number = int(url.path())
        except ValueError:
            return
        if (a := self.quick_action(action_number)) is not None:
            tip = ''
            if kind := quick_action_kind_name(a.kind):
                tip = _('Kind of action: {}').format(kind) + '<br>'
            if action_number < MAX_QUICK_ACTION_SHORTCUTS:
                tip += _('Shortcut: {}').format(f'Ctrl+{action_number + 1}') + '<br>'
            tip += _('Click twice to take this action: once to put it in the box below, again to send it to the AI')
            QToolTip.showText(QCursor.pos(), f'<p>{tip}', self.story_view)
        else:
            QToolTip.hideText()

    def copy_current_turn(self) -> None:
        # Copy the turn being read, along with the quick actions when it is
        # the last turn, to the clipboard as both rich and plain text, with
        # the picture of its scene, if any.
        state = self.state
        tn = self.visible_turn_number()
        if state is None or not tn:
            return
        t = state.turns[tn - 1]
        text_parts: list[str] = []
        html_parts: list[str] = []
        if t.player_input:
            text_parts.append(f'➤ {t.player_input}')
            html_parts.append(f'<p><i>➤ {escape(t.player_input)}</i></p>')
        text_parts.append(t.turn.narrative)
        html_parts.append(response_to_html(t.turn.narrative, ContentType.markdown))
        if tn == len(state.turns) and t.turn.quick_actions:
            text_parts.append(_('Quick actions') + ':\n' + '\n'.join(f'• {quick_action_as_text(a)}' for a in t.turn.quick_actions))
            html_parts.append(f'<h4>{_("Quick actions")}</h4>' + ''.join(f'<p>• {escape(a.text)}{quick_action_kind_html(a)}</p>' for a in t.turn.quick_actions))
        md = QMimeData()
        md.setText('\n\n'.join(text_parts))
        md.setHtml(''.join(html_parts))
        img, scene = self.images.get(tn), QImage()
        has_image = img is not None and scene.loadFromData(img.data)
        if has_image:
            md.setImageData(scene)
        clipboard = qapplication_or_fail().clipboard()
        assert clipboard is not None
        clipboard.setMimeData(md)
        if has_image:
            self.status_bar.showMessage(_('Copied the text and scene picture of turn {} to the clipboard').format(tn), 5000)
        else:
            self.status_bar.showMessage(_('Copied the text of turn {} to the clipboard').format(tn), 5000)

    def scroll_to_turn(self, turn_number: int) -> None:
        if not self.isVisible():
            # While the widget is hidden the story document is laid out for
            # the wrong geometry, so scrolling now would land in the wrong
            # place; deferred until showEvent().
            self.pending_scroll_turn = turn_number
            return
        self.pending_scroll_turn = 0
        self.story_view.stopMomentumScroll()
        for pos, tn in self.turn_positions:
            if tn == turn_number:
                sv = self.story_view
                c = sv.textCursor()
                c.setPosition(pos)
                sv.setTextCursor(c)
                sv.ensureCursorVisible()
                vsb = sv.verticalScrollBar()
                if vsb is not None:  # align the start of the turn with the top of the view
                    vsb.setValue(vsb.value() + sv.cursorRect().top())
                break

    def visible_turn_number(self) -> int:
        # The one based number of the turn the player is currently reading,
        # 0 when no turns are displayed. That is the turn covering the
        # largest part of the viewport, so that slight scrolling does not
        # flip between turns, except when the view is scrolled to the end:
        # the last turn is usually too short to cover most of the view, but
        # it is what the player is reading.
        if not self.turn_positions:
            return 0
        sv = self.story_view
        vsb = sv.verticalScrollBar()
        vp = sv.viewport()
        if vsb is None or vp is None or vsb.value() >= vsb.maximum():
            return self.turn_positions[-1][1]
        height = vp.height()
        # Only the turns intersecting the viewport, found by mapping the
        # viewport top and bottom to document positions, need their pixel
        # geometry computed, keeping this cheap however long the chapter is.
        starts = [pos for pos, tn in self.turn_positions]
        first = max(0, bisect_right(starts, sv.cursorForPosition(QPoint(5, 0)).position()) - 1)
        last = max(0, bisect_right(starts, sv.cursorForPosition(QPoint(5, height - 1)).position()) - 1)
        c = sv.textCursor()

        def top_of(idx: int) -> int:
            # The viewport y coordinate at which turn_positions[idx] starts,
            # clamped to the viewport bottom for turns known to start at or
            # below it and for the end of the story.
            if idx > last or idx >= len(self.turn_positions):
                return height
            c.setPosition(self.turn_positions[idx][0])
            return sv.cursorRect(c).top()

        ans, best_overlap = self.turn_positions[first][1], 0
        top = top_of(first)
        for i in range(first, last + 1):
            bottom = top_of(i + 1)
            overlap = min(bottom, height) - max(top, 0)
            if overlap >= best_overlap:  # ties go to the later turn
                ans, best_overlap = self.turn_positions[i][1], overlap
            top = bottom
        return ans

    def on_story_scrolled(self) -> None:
        self.scroll_settle_timer.start()

    # }}}

    # Scene panel and status displays {{{

    def update_scene_panel(self) -> None:
        state = self.state
        if state is None:
            return
        if not self.images_enabled:
            html = f'<h3>{escape(state.world.title)}</h3>'
            html += response_to_html(state.world.world_description, ContentType.markdown)
            if html != self.info_view.property('cyoa-html'):  # avoid losing the scroll position on every update
                self.info_view.setProperty('cyoa-html', html)
                self.info_view.setHtml(html)
            return
        tn = self.visible_turn_number()
        img = self.images.get(tn)
        busy = bool(tn) and tn == self.image_turn
        failed = img is None and not busy and tn in self.failed_image_turns
        can_generate = bool(tn) and img is None and not busy and not failed
        if busy:
            placeholder = _('Generating a picture of this scene…')
        elif failed or can_generate:
            placeholder = ''  # the scene image display shows its retry/generate panel instead
        else:
            placeholder = _('No picture of this scene is available')
        self.scene_image.set_image(img.data if img else None, placeholder, failed=failed, busy=busy, can_generate=can_generate)

    def displayed_scene_image(self) -> data.SceneImage | None:
        # The picture of the turn the player is currently reading, if any.
        tn = self.visible_turn_number()
        return self.images.get(tn) if tn else None

    def show_scene_image_popup(self) -> None:
        img = self.displayed_scene_image()
        if img is None:
            return
        pm = QPixmap()
        if not pm.loadFromData(img.data):
            return
        self.image_popup.current_img = pm
        self.image_popup.current_url = QUrl(data.image_file_name(self.visible_turn_number()))
        self.image_popup()

    def copy_scene_image(self) -> None:
        img = self.displayed_scene_image()
        if img is None:
            self.status_bar.showMessage(_('There is no picture of the current scene to copy'), 5000)
            return
        pm = QPixmap()
        if pm.loadFromData(img.data):
            clipboard = qapplication_or_fail().clipboard()
            assert clipboard is not None
            clipboard.setPixmap(pm)
            self.status_bar.showMessage(_('Copied the picture of the scene to the clipboard'), 5000)

    def show_scene_image_context_menu(self, pos: QPoint) -> None:
        m = QMenu(self.scene_image)
        m.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        m.addAction(self.copy_image_action)
        m.addAction(self.popup_image_action)
        img = self.displayed_scene_image()
        can_regen = self.image_call == -1 and bool(self.visible_turn_number())
        self.edit_image_prompt_action.setEnabled(bool(can_regen and img))
        m.addAction(self.edit_image_prompt_action)
        m.exec(pos)

    def edit_scene_image_prompt(self) -> None:
        tn = self.visible_turn_number()
        if not tn or self.state is None:
            return
        img = self.displayed_scene_image()
        if img and img.prompt:
            current_prompt = img.prompt
        else:
            current_prompt = scene_image_prompt(self.state.turns[tn - 1].turn.scene_description, self.state.art_style)
        d = QDialog(self)
        d.setWindowTitle(_('Edit image prompt'))
        d.resize(700, 400)
        l = QVBoxLayout(d)
        la = QTextEdit(d)
        la.setPlainText(current_prompt)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, d)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        l.addWidget(la)
        l.addWidget(bb)
        if d.exec() == QDialog.DialogCode.Accepted:
            prompt = la.toPlainText().strip()
            if prompt:
                self.request_image(tn, prompt=prompt)

    def update_window_title(self) -> None:
        w = self.window()
        if w is None or self.state is None:
            return
        title = self.state.world.title
        if self.state.turns:
            title += ' - ' + self.state.chapter_titles[self.state.current_chapter]
        w.setWindowTitle(title)

    def update_status(self) -> None:
        state = self.state
        if state is None:
            self.status_label.setText('')
            return
        parts = [_('Turn: {}').format(len(state.turns)), _('Chapter: {}').format(state.current_chapter + 1)]
        currency = ''
        total_cost = 0.0
        for t in state.turns:
            total_cost += t.cost
            currency = currency or t.currency
        for img in self.images.values():
            total_cost += img.cost
            currency = currency or img.currency
        model_parts: list[str] = []
        for kind in ('text', 'image'):
            m = data.configured_model_name(kind) or data.configured_provider_name(kind)
            if m:
                model_parts.append(m)
        if model_parts:
            parts.append(_('Models: {}').format(', '.join(model_parts)))
        if total_cost or self.session_cost:
            parts.append(_('Cost: {0} this session, {1} in total').format(fmt_cost(self.session_cost, currency), fmt_cost(total_cost, currency)))
        self.status_label.setText(' · '.join(parts))

    # }}}

    # Playing turns {{{

    def take_action(self) -> None:
        if self.state is None:
            return
        player_input = self.prompt_edit.toPlainText().strip()
        if not player_input and self.state.turns:
            error_dialog(
                self,
                _('No action'),
                _('Type the action you want to take, or click one of the quick action links or the "Something interesting happens" button.'),
                show=True,
            )
            return
        self.request_turn(player_input)

    def interesting_event(self) -> None:
        self.request_turn('', interesting_event=True)

    def on_turn_timeout(self) -> None:
        if self.turn_call < 0 or self.turn_request is None:
            return
        turn_request = self.turn_request
        thinking_start = self._thinking_start
        # The turn is still in flight and still paid for, so its call number
        # is deliberately left alone: a result that arrives while the dialog
        # below is open is stashed by on_turn_result() and applied afterwards.
        self.turn_timed_out = True
        self._stop_thinking()
        timeout_minutes = data.turn_timeout_minutes()
        d = error_dialog(
            self,
            _('AI response timed out'),
            ngettext('The AI did not respond within {} minute.', 'The AI did not respond within {} minutes.', timeout_minutes).format(timeout_minutes),
        )
        should_retry = [False]
        should_wait = [False]
        retry_btn = d.bb.addButton(_('&Retry'), QDialogButtonBox.ButtonRole.ActionRole)
        retry_btn.setIcon(QIcon.ic('view-refresh.png'))
        wait_btn = d.bb.addButton(_('&Wait longer'), QDialogButtonBox.ButtonRole.ActionRole)
        wait_btn.setIcon(QIcon.ic('jobs.png'))

        timeout_widget = QWidget(d)
        timeout_layout = QHBoxLayout(timeout_widget)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        timeout_label = QLabel(_('&Timeout (minutes, 0 = no timeout):'), timeout_widget)
        timeout_spin = QSpinBox(timeout_widget)
        timeout_spin.setRange(0, 60)
        timeout_spin.setValue(timeout_minutes)
        timeout_label.setBuddy(timeout_spin)
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(timeout_spin)
        timeout_layout.addStretch()
        d.gridLayout.removeWidget(d.bb)
        d.gridLayout.addWidget(timeout_widget, 3, 0, 1, 2)
        d.gridLayout.addWidget(d.bb, 4, 0, 1, 2)

        def on_retry() -> None:
            should_retry[0] = True
            d.accept()

        def on_wait() -> None:
            should_wait[0] = True
            d.accept()

        retry_btn.clicked.connect(on_retry)
        wait_btn.clicked.connect(on_wait)
        self.turn_timeout_dialog = d
        try:
            d.exec()
        finally:
            self.turn_timeout_dialog = None
            self.turn_timed_out = False
        new_timeout = timeout_spin.value()
        data.set_turn_timeout_minutes(new_timeout)
        if (late := self.late_turn_result) is not None:
            # The turn arrived while this dialog was open. It is complete and
            # paid for, so apply it whatever the player chose in the dialog.
            self.late_turn_result = None
            self.on_turn_result(*late)
            return
        if should_wait[0]:
            self._thinking_start = thinking_start
            self._update_thinking_elapsed()
            self.input_stack.start()
            self._thinking_ticker.start()
            if new_timeout > 0:
                self.turn_timer.setInterval(new_timeout * 60 * 1000)
                self.turn_timer.start()
            return
        # The player gave up on this turn, so a result for it is now stale
        self.turn_call = -1
        self.turn_request = None
        self.discard_pending_turn_display()
        if should_retry[0]:
            player_input, interesting_event = turn_request
            self.request_turn(player_input, interesting_event)

    def request_turn(self, player_input: str, interesting_event: bool = False) -> None:
        if self.state is None or self.turn_call > -1:
            return
        plugin = self.plugin_override or data.plugin_for('text')
        if plugin is None:
            error_dialog(self, _('No AI configured'), _('No AI for text generation has been configured for the game.'), show=True)
            return
        # Play the turn on a copy so that rewinding/loading while the AI is
        # generating cannot corrupt the current game state.
        snapshot = deserialize_game(serialize_game(self.state))
        self.turn_call = next(self.turn_counter)
        self.turn_request = (player_input, interesting_event)
        self.streamed_narrative = ''
        self._thinking_start = monotonic()
        self.input_stack.msg = _('Thinking…')
        self.input_stack.start()
        self._thinking_ticker.start()
        timeout = data.turn_timeout_minutes()
        if timeout > 0:
            self.turn_timer.setInterval(timeout * 60 * 1000)
            self.turn_timer.start()
        # Show the action being taken where the prose of the turn will appear
        # as the AI writes it, see on_turn_narrative()
        self.render_story()
        if (vsb := self.story_view.verticalScrollBar()) is not None:
            vsb.setValue(vsb.maximum())
        Thread(name='CYOATurn', daemon=True, target=self.do_turn, args=(snapshot, player_input, interesting_event, self.turn_call, plugin)).start()

    def do_turn(self, snapshot: GameState, player_input: str, interesting_event: bool, call_number: int, plugin: AIProvider) -> None:
        def on_narrative(text: str) -> None:
            if not sip.isdeleted(self):
                self.turn_narrative_received.emit(call_number, text)

        try:
            # the preferences overlay is thread local so must be entered here
            with data.cyoa_ai_settings():
                res = next_turn(snapshot, player_input, plugin, interesting_event=interesting_event, on_narrative=on_narrative)
            if sip.isdeleted(self):
                return
            self.turn_result_received.emit(call_number, snapshot, res)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_turn_narrative(self, call_number: int, text: str) -> None:
        if call_number != self.turn_call:
            return  # a stale fragment from a superseded or cancelled call
        first = not self.streamed_narrative
        self.streamed_narrative += text
        if first:
            self._update_thinking_elapsed()  # switch to "Writing…"
        # An AI that is writing has not stopped responding, so the timeout
        # is measured from the last fragment received rather than from the
        # start of the turn.
        if self.turn_timer.isActive():
            self.turn_timer.start()
        if not self.narrative_render_timer.isActive():
            self.narrative_render_timer.start()

    def on_turn_result(self, call_number: int, snapshot: GameState, res: StructuredOutputResult) -> None:
        if call_number != self.turn_call:
            return  # a stale result from a superseded or cancelled call
        if self.turn_timed_out:
            # The timeout dialog is asking the player what to do about this
            # very turn, so keep the result and let on_turn_timeout() apply it
            # once the dialog is closed instead of changing the game behind it.
            self.late_turn_result = (call_number, snapshot, res)
            if (d := self.turn_timeout_dialog) is not None:
                d.accept()
            return
        self.turn_timer.stop()
        turn_request = self.turn_request
        self.turn_call = -1
        self.turn_request = None
        self._stop_thinking()
        if res.exception is not None:
            self.discard_pending_turn_display()
            d = error_dialog(
                self,
                _('Failed to generate the next turn'),
                _('The AI failed to continue the story: {}').format(res.exception),
                det_msg=res.error_details,
            )
            should_retry = [False]
            retry_btn = d.bb.addButton(_('&Retry'), QDialogButtonBox.ButtonRole.ActionRole)
            retry_btn.setIcon(QIcon.ic('view-refresh.png'))

            def on_retry() -> None:
                should_retry[0] = True
                d.accept()

            retry_btn.clicked.connect(on_retry)
            d.exec()
            if should_retry[0] and turn_request is not None:
                player_input, interesting_event = turn_request
                self.request_turn(player_input, interesting_event)
            return
        self.state = snapshot
        self.session_cost += res.cost
        self.streamed_narrative = ''
        self.narrative_render_timer.stop()
        self.prompt_edit.clear()
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.autosave()
        self.refresh_ui()
        if self.images_enabled:
            self.request_image(len(snapshot.turns))
        self._notify_turn_ready()

    def _notify_turn_ready(self) -> None:
        w = self.window()
        if w is None:
            return
        if w.isVisible() and w.isActiveWindow():
            return
        if not w.isVisible():
            w.show()
        w.raise_and_focus()
        if not config['disable_tray_notification']:
            from calibre.gui2.notify import get_notifier

            notifier = get_notifier()
            if notifier is not None:
                state = self.state
                summary = state.world.title if state is not None else None
                notifier(_('Your adventure turn is ready'), summary=summary)

    # }}}

    # Scene image generation {{{

    def apply_images_enabled(self) -> None:
        self.scene_image.setVisible(self.images_enabled)
        self.scene_filler.setVisible(self.images_enabled)
        self.info_view.setVisible(not self.images_enabled)
        # The checkbox sits directly under the scene image when images are
        # on and at the bottom of the panel, under the world info, when off.
        rl = self.right_panel_layout
        rl.removeWidget(self.images_check)
        rl.insertWidget(1 if self.images_enabled else rl.count(), self.images_check)
        self.update_scene_panel()

    def toggle_images(self) -> None:
        enabled = self.images_check.isChecked()
        if enabled and not data.is_ready('image'):
            if ConfigureImageAIDialog(self).exec() != Dialog.DialogCode.Accepted or not data.is_ready('image'):
                self.images_check.setChecked(False)
                return
        data.mark_image_skipped(not enabled)
        self.images_enabled = enabled
        if not enabled:
            # Discard any in-flight image generation, its result no longer
            # matches image_call when it arrives.
            self.image_call = -1
            self.image_turn = -1
        self.apply_images_enabled()
        self.update_status()  # a new image AI may have been configured above
        state = self.state
        if enabled and state is not None and state.turns and len(state.turns) not in self.images:
            self.request_image(len(state.turns))

    def request_image(self, turn_number: int, prompt: str = '') -> None:
        state = self.state
        if state is None or not self.images_enabled or not 0 < turn_number <= len(state.turns):
            return
        plugin = data.plugin_for('image')
        if plugin is None:
            return
        if not prompt:
            prompt = scene_image_prompt(state.turns[turn_number - 1].turn.scene_description, state.art_style)
        self.image_call = next(self.image_counter)
        self.image_turn = turn_number
        Thread(name='CYOASceneImage', daemon=True, target=self.do_generate_image, args=(prompt, turn_number, self.image_call, plugin)).start()
        self.update_scene_panel()

    def do_generate_image(self, prompt: str, turn_number: int, call_number: int, plugin: AIProviderPlugin) -> None:
        try:
            # the preferences overlay is thread local so must be entered here
            with data.cyoa_ai_settings():
                res = plugin.generate_image(prompt, options=ImageGenerationOptions(aspect_ratio='4:3'))
            image: data.SceneImage | None = None
            error, error_details = '', ''
            if res.exception is not None:
                error, error_details = str(res.exception), res.error_details
            elif not res.image:
                error = _('The AI did not return an image')
            else:
                try:
                    img = resize_to_fit(image_from_data(res.image.data), SCENE_IMAGE_SIZE, SCENE_IMAGE_SIZE)[1]
                    webp = image_to_data(img, compression_quality=70, fmt='WEBP')
                    image = data.SceneImage(data=webp, cost=res.cost, currency=res.currency, provider=res.provider, model=res.model, prompt=prompt)
                except Exception as e:
                    error = str(e)
            if sip.isdeleted(self):
                return
            self.image_result_received.emit(call_number, turn_number, SceneImageResult(image, error, error_details))
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_image_result(self, call_number: int, turn_number: int, res: SceneImageResult) -> None:
        if call_number != self.image_call:
            return  # a stale result from a superseded or cancelled call
        self.image_call = -1
        self.image_turn = -1
        if res.image is None:
            self.failed_image_turns.add(turn_number)
            self.status_bar.showMessage(_('Failed to generate a picture of the scene: {}').format(res.error), 10000)
        else:
            self.failed_image_turns.discard(turn_number)
            self.images[turn_number] = res.image
            self.session_cost += res.image.cost
            self.autosave()
        self.update_status()
        self.update_scene_panel()

    def regenerate_scene_image(self) -> None:
        # (Re-)generate the picture of the turn the player is currently
        # reading, replacing any existing picture, triggered by the refresh,
        # retry and generate buttons on the scene image display.
        if self.image_call > -1:
            self.status_bar.showMessage(_('A picture of a scene is already being generated, please wait.'), 5000)
            return
        if tn := self.visible_turn_number():
            self.request_image(tn)

    # }}}

    # Saving, loading and rewinding {{{

    def autosave(self) -> None:
        if not self.game_id or self.state is None:
            return
        try:
            data.save_game(self.game_id, self.state, self.images, portraits=self.portraits)
        except Exception as e:
            self.status_bar.showMessage(_('Failed to auto-save the game: {}').format(e), 10000)

    def save_game_as(self) -> None:
        if self.state is None:
            return
        d = SaveGameDialog(self.last_save_name, self)
        if d.exec() != Dialog.DialogCode.Accepted:
            return
        name = d.save_name
        try:
            data.save_game(name, self.state, self.images, base=data.saves_dir(), portraits=self.portraits)
        except Exception as e:
            error_dialog(self, _('Failed to save game'), _('Failed to save the game: {}').format(e), show=True)
            return
        self.last_save_name = name
        self.status_bar.showMessage(_('Game saved as "{}"').format(name), 5000)

    def load_saved_game(self) -> None:
        d = LoadGameDialog(self)
        if d.exec() != Dialog.DialogCode.Accepted or not d.save_name:
            return
        if not question_dialog(
            self, _('Are you sure?'), _('Loading the saved game "{}" will replace the current game. Any unsaved progress will be lost.').format(d.save_name)
        ):
            return
        try:
            state, images, portraits = data.load_game(d.save_name, base=data.saves_dir())
        except Exception as e:
            error_dialog(self, _('Failed to load game'), _('Failed to load the saved game "{0}": {1}').format(d.save_name, e), show=True)
            return
        self.cancel_pending_ai_calls()
        self.state = state
        self.images = images
        self.failed_image_turns = set()
        self.portraits = portraits
        self.last_save_name = d.save_name
        self.autosave()
        self.refresh_ui()
        if not state.turns:
            self.request_turn('')

    def rewind_to_turn(self, turn_number: int) -> None:
        state = self.state
        if state is None or not 0 < turn_number < len(state.turns):
            return
        self.cancel_pending_ai_calls()
        rewind(state, len(state.turns) - turn_number)
        self.images = {k: v for k, v in self.images.items() if k <= turn_number}
        self.failed_image_turns = {t for t in self.failed_image_turns if t <= turn_number}
        self.autosave()
        self.refresh_ui()

    def restart_game(self) -> None:
        state = self.state
        if state is None or len(state.turns) < 2:
            self.status_bar.showMessage(_('The adventure is already at its first turn.'), 5000)
            return
        if question_dialog(
            self, _('Are you sure?'), _('Restart the adventure from the first turn? All later turns are discarded and any unsaved progress will be lost.')
        ):
            self.rewind_to_turn(1)

    def back_to_turn(self) -> None:
        state = self.state
        if state is None or len(state.turns) < 2:
            self.status_bar.showMessage(_('There are no earlier turns to go back to.'), 5000)
            return
        max_back = len(state.turns) - 1
        num, ok = QInputDialog.getInt(self, _('Back to turn'), _('Number of turns to go back (1 to {}):').format(max_back), 1, 1, max_back)
        if ok:
            self.go_back(num)

    def go_back(self, num_turns: int = 1) -> None:
        state = self.state
        if state is None or len(state.turns) < 2:
            self.status_bar.showMessage(_('There are no earlier turns to go back to.'), 5000)
            return
        target = len(state.turns) - min(num_turns, len(state.turns) - 1)
        if question_dialog(
            self, _('Are you sure?'), _('Go back to turn {}? All turns after it are discarded and any unsaved progress will be lost.').format(target)
        ):
            self.rewind_to_turn(target)

    def exit_to_world_generation(self) -> None:
        if question_dialog(
            self,
            _('Are you sure?'),
            _('Leave this game and return to the world creation screen? Any unsaved progress will be lost. Use the Save button to keep this game.'),
        ):
            self.game_abandoned.emit()

    def edit_world(self) -> None:
        state = self.state
        if state is None:
            return
        d = EditWorldDialog(state, self.portraits, self)
        if d.exec() != Dialog.DialogCode.Accepted:
            return
        self.portraits = d.portraits
        # The world holds the only copy of the played character, which
        # state.character is a view of.
        chars = list(state.world.characters)
        chars[state.character_index] = d.player_character
        state.world = state.world._replace(characters=tuple(chars))
        # Apply the edits to the summaries of all stored turns, matching by
        # the stable character ids, so that they survive rewinding the game
        # and apply to a character the player renamed here.
        if edits := {c.id: c for c in d.npcs if c.id}:
            for i, t in enumerate(state.turns):
                characters = tuple(edits.get(c.id, c) for c in t.summary.characters)
                if characters != t.summary.characters:
                    state.turns[i] = t._replace(summary=t.summary._replace(characters=characters))
        # The story memory, unlike the characters, is a snapshot of where the
        # story stands, so it is applied to the last turn alone: going back to
        # an earlier turn must restore the memory as it was at that turn.
        if (memory := d.story_memory) is not None:
            t = state.turns[-1]
            state.turns[-1] = t._replace(
                summary=t.summary._replace(
                    world=memory.world,
                    major_events=memory.major_events,
                    current_situation=memory.current_situation,
                    upcoming_events=memory.upcoming_events,
                )
            )
        # The saved world the game started from is only its template, so it is
        # deliberately left alone: the edited characters and their portraits
        # belong to this game and are stored with it.
        self.autosave()
        self.status_bar.showMessage(_('Changes to the world will be used from the next turn'), 5000)

    def change_settings(self) -> None:
        if SettingsDialog(self).exec() != Dialog.DialogCode.Accepted:
            return
        # The image AI may have been enabled, disabled or changed, so re-sync
        # the scene panel with the new settings, as toggle_images() does.
        self.images_enabled = data.images_enabled()
        self.images_check.setChecked(self.images_enabled)
        if not self.images_enabled:
            # Discard any in-flight image generation, its result no longer
            # matches image_call when it arrives.
            self.image_call = -1
            self.image_turn = -1
        self.apply_images_enabled()
        self.refresh_text_display()
        self.update_status()  # show the newly configured models in the status bar
        state = self.state
        if self.images_enabled and state is not None and state.turns and len(state.turns) not in self.images:
            self.request_image(len(state.turns))
        self.status_bar.showMessage(_('The changed AI settings will be used from the next turn'), 5000)

    # }}}


if __name__ == '__main__':
    import json

    from calibre.ai.cyoa import (
        PROTAGONIST_ID,
        CharacterDelta,
        GeneratedWorld,
        PlayerCharacter,
        QuickActionKind,
        StoryTurn,
        SummaryUpdate,
        as_jsonable,
        start_game,
    )
    from calibre.ai.structured import OnText, spec_for_class
    from calibre.gui2 import Application

    class FakePlugin:
        # Plays canned turns so the widget can be exercised without an AI,
        # streaming their JSON a few characters at a time like an AI would
        counter = count(start=1)

        def generate_structured_output(
            self, prompt: str, schema: type, instructions: str = '', use_model: str = '', on_text: OnText | None = None
        ) -> StructuredOutputResult:
            import time

            time.sleep(1)
            n = next(self.counter)
            turn = StoryTurn(
                narrative=f'**Turn {n}**: The mist *swirls* around you as something stirs in the distance.\n\nYou must decide quickly.'
                + ' The fog thickens with every breath you take, and somewhere ahead a bell begins to toll.' * 3,
                quick_actions=(
                    QuickAction(f'Wait and watch (turn {n})', QuickActionKind.cautious),
                    QuickAction('Charge into the mist', QuickActionKind.bold),
                    QuickAction('Call out to whoever is there', QuickActionKind.social),
                ),
                scene_description='A foggy city street at night.',
                summary_update=SummaryUpdate(
                    current_situation='In the mist.',
                    character_updates=(
                        CharacterDelta(
                            id=PROTAGONIST_ID,
                            current_state='standing in the rain outside the depot',
                            name='Ada',
                            description='the player',
                            backstory='She built the mist engines.',
                            relationships='alone so far',
                        ),
                        CharacterDelta(
                            id='marlo',
                            current_state='waiting at the tunnel mouth, out of breath',
                            name='Marlo',
                            description='a mist-runner who guides travelers',
                            backstory='He grew up in the tunnels under the city.',
                            relationships="wary of Ada's engines",
                        ),
                    ),
                    new_major_events=(f'event {n}',),
                    upcoming_events=('The mist thickens.',),
                ),
                starts_new_chapter=n > 1 and (n % 4) == 0,
                chapter_title=f'Chapter of turn {n}' if n > 1 and (n % 4) == 0 else None,
            )
            raw = json.dumps(as_jsonable(turn, spec_for_class(StoryTurn)))
            if on_text is not None:
                for i in range(0, len(raw), 6):
                    on_text(raw[i : i + 6])
                    time.sleep(0.02)
            return StructuredOutputResult(data=turn, raw=raw, cost=0.01 * n, currency='USD', provider='fake', model='fake-model')

    app = Application([])
    w = GameWidget()
    w.plugin_override = FakePlugin()
    pc = PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.')
    world = GeneratedWorld(title='Mist City', world_description='A city lost in *perpetual* mist.', characters=(pc,))
    # An empty game_id disables auto-saving, so the demo does not touch the
    # calibre config directory.
    w.load_game('', start_game('a foggy city', world))
    w.game_abandoned.connect(lambda: print('game abandoned'))
    w.resize(1000, 720)
    w.show()
    app.exec()
    del w
    del app
