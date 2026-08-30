#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The gameplay widget of the "Create Your Own Adventure" game. The story of
# the current chapter is shown turn-by-turn in a text browser with a prompt
# box below it to enter the action to take. A picture of the scene currently
# scrolled into view is shown on the right, when an image AI is configured.
# The game is auto-saved after every turn; the toolbar allows saving under a
# name of the player's choosing, loading such saves, rewinding, turning
# scene images on/off and starting over in a new world.

import os
from collections.abc import Callable
from functools import partial
from html import escape
from itertools import count
from threading import Thread
from time import localtime, strftime
from typing import NamedTuple

from qt.core import (
    QAction,
    QCursor,
    QDialogButtonBox,
    QHBoxLayout,
    QIcon,
    QInputDialog,
    QKeyEvent,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPainter,
    QPaintEvent,
    QPixmap,
    QPlainTextEdit,
    QPoint,
    QPushButton,
    QRectF,
    QShortcut,
    QShowEvent,
    QSize,
    QSizeF,
    QSplitter,
    QStatusBar,
    Qt,
    QTextBlockFormat,
    QTextBrowser,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
    QToolBar,
    QToolTip,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
    sip,
)

from calibre.ai import AICapabilities, ImageGenerationOptions, StructuredOutputResult
from calibre.ai.config import AIConfigWidget, ConfigureAI
from calibre.ai.cyoa import AIProvider, GameOutcome, GameState, deserialize_game, next_turn, rewind, scene_image_prompt, serialize_game
from calibre.ai.utils import ContentType, response_to_html
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog, question_dialog, safe_open_url
from calibre.gui2.cyoa import data
from calibre.gui2.progress_indicator import WaitStack
from calibre.gui2.widgets2 import Dialog
from calibre.utils.img import image_from_data, image_to_data, resize_to_fit
from calibre.utils.localization import _, ngettext

QUICK_ACTION_SCHEME = 'quick-action'
# Quick action number i is activated by pressing Ctrl+(i+1)
MAX_QUICK_ACTION_SHORTCUTS = 9
SAVE_NAME_ROLE = Qt.ItemDataRole.UserRole
# Scene images are stored downscaled to fit this many pixels in either
# dimension, keeping saved games reasonably small.
SCENE_IMAGE_SIZE = 1280


def fmt_cost(cost: float, currency: str) -> str:
    return f'{cost:.4f} {currency}'.strip()


def insert_html_block(c: QTextCursor, html: str) -> None:
    # QTextCursor.insertHtml() merges the first block of the fragment into
    # the current block, which inherits its block format. Sequential calls
    # thus run text into the preceding heading and attach the ruler of a
    # preceding <hr> to the following paragraph, so start every fragment in
    # a fresh block with default formatting.
    if c.position():
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
    c.insertHtml(html)


def fmt_timestamp(ts: float) -> str:
    return strftime('%d %b %Y, %H:%M', localtime(ts))


class SceneImageResult(NamedTuple):
    # The outcome of generating the picture of one turn's scene.
    image: data.SceneImage | None
    error: str = ''
    error_details: str = ''


# Saved game dialogs {{{


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


# }}}


class ConfigureImageAIDialog(Dialog):
    # Asks the player to configure the AI used to generate pictures of each
    # scene, saving the settings the same way as the welcome screen.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Configure image AI'), 'cyoa-configure-image-ai', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.msg_label = la = QLabel(
            '<p>' + _('No AI for image generation has been configured for the game. To show pictures of each scene, configure one below:')
        )
        la.setWordWrap(True)
        l.addWidget(la)
        # Construct the provider config widget inside the CYOA settings
        # overlay so it displays the settings used for the game, with API
        # keys falling through to the common AI preferences.
        with data.cyoa_ai_settings():
            self.image_config = ic = ConfigureAI(
                AICapabilities.text_to_image,
                parent=self,
                save_hook=self.save_image_settings,
                initial_provider_name=data.configured_provider_name('image'),
            )
        l.addWidget(ic)
        l.addWidget(self.bb)

    def save_image_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('image', plugin.name, config_widget.settings)

    def accept(self) -> None:
        if not self.image_config.commit():
            return
        super().accept()


class PromptEdit(QPlainTextEdit):
    # The box the player types their next action into. Ctrl+Enter submits.
    submit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMaximumHeight(self.fontMetrics().lineSpacing() * 4)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            e.accept()
            self.submit_requested.emit()
            return
        super().keyPressEvent(e)


class SceneImageDisplay(QWidget):
    # Shows an image scaled to fit while preserving aspect ratio, or a
    # placeholder message when there is no image.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_data = b''
        self.placeholder = ''
        self.pixmap = QPixmap()

    def set_image(self, image_data: bytes | None, placeholder: str) -> None:
        image_data = image_data or b''
        if image_data == self.image_data and placeholder == self.placeholder:
            return
        self.image_data, self.placeholder = image_data, placeholder
        pm = QPixmap()
        if image_data:
            pm.loadFromData(image_data)
            pm.setDevicePixelRatio(self.devicePixelRatioF())
        self.pixmap = pm
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 400)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        p = QPainter(self)
        if self.pixmap.isNull():
            to = QTextOption(Qt.AlignmentFlag.AlignCenter)
            to.setWrapMode(QTextOption.WrapMode.WordWrap)
            p.drawText(QRectF(self.rect()), self.placeholder, to)
        else:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            sz = QSizeF(self.pixmap.deviceIndependentSize())
            sz.scale(QSizeF(self.size()), Qt.AspectRatioMode.KeepAspectRatio)
            r = QRectF(0, 0, sz.width(), sz.height())
            r.moveCenter(QRectF(self.rect()).center())
            r.moveTop(0)  # centered horizontally, aligned with the panel top
            p.drawPixmap(r, self.pixmap, QRectF(self.pixmap.rect()))
        p.end()


class GameWidget(QWidget):
    game_abandoned = pyqtSignal()

    turn_result_received = pyqtSignal(int, object, object)  # (call_number, GameState the turn was played on, StructuredOutputResult)
    image_result_received = pyqtSignal(int, int, object)  # (call_number, turn number, SceneImageResult)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game_id = ''
        self.state: GameState | None = None
        self.images: dict[int, data.SceneImage] = {}  # keyed by one based turn number
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
        self.image_counter = count(start=1)
        self.image_call = -1
        self.image_turn = -1
        # (document position, one based turn number) of every turn shown in
        # the story view, used to map the scroll position to a turn.
        self.turn_positions: list[tuple[int, int]] = []
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
        self.jump_action = toolbar_action(
            'edit-undo.png', _('Jump to turn'), _('Rewind the adventure to an earlier turn, discarding all turns after it'), self.jump_to_turn
        )
        self.images_action = toolbar_action(
            'view-image.png',
            _('Images'),
            _('Show AI generated pictures of each scene. When turned off, no images are generated for new turns'),
            self.toggle_images,
        )
        self.images_action.setCheckable(True)
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
        self.story_view = sv = QTextBrowser(left)
        sv.setOpenLinks(False)
        doc = sv.document()
        if doc is not None:  # quick action links are colored but not underlined
            doc.setDefaultStyleSheet('a { text-decoration: none }')
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
        ab.setToolTip('<p>' + _('Submit your action to the AI game master. You can also press {} in the box above').format('Ctrl+Enter'))
        ab.clicked.connect(self.take_action)
        h.addWidget(ab)
        self.interesting_button = ib = QPushButton(QIcon.ic('ai.png'), _('Something &interesting happens'), input_panel)
        ib.setToolTip('<p>' + _('Instead of taking an action yourself, have the AI make something unexpected and interesting happen next'))
        ib.clicked.connect(self.interesting_event)
        h.addWidget(ib), h.addStretch()
        il.addLayout(h)
        self.input_stack = ws = WaitStack(_('The AI is writing what happens next…'), after=input_panel, parent=left, size=64)
        ws.stop()
        ll.addWidget(ws)
        sp.addWidget(left)

        right = QWidget(sp)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.scene_image = si = SceneImageDisplay(right)
        rl.addWidget(si, stretch=10)
        self.condition_label = cl = QLabel(right)
        cl.setWordWrap(True)
        cl.setTextFormat(Qt.TextFormat.RichText)
        rl.addWidget(cl)
        self.info_view = iv = QTextBrowser(right)  # shown instead of the image when the image AI is disabled
        rl.addWidget(iv, stretch=10)
        sp.addWidget(right)
        sp.setStretchFactor(0, 3)
        sp.setStretchFactor(1, 1)
        l.addWidget(sp, stretch=10)

        self.status_bar = sb = QStatusBar(self)
        sb.setSizeGripEnabled(False)
        self.status_label = sl = QLabel(sb)
        sb.addPermanentWidget(sl)
        l.addWidget(sb)

        # Ctrl+1, Ctrl+2, … activate the corresponding quick action link
        for i in range(MAX_QUICK_ACTION_SHORTCUTS):
            sc = QShortcut(QKeySequence(f'Ctrl+{i + 1}'), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(partial(self.activate_quick_action, i))

        # Focus given to this widget, e.g. when it becomes the visible page
        # of the main window, goes to the box the player types into.
        self.setFocusProxy(self.prompt_edit)

        self.turn_result_received.connect(self.on_turn_result, type=Qt.ConnectionType.QueuedConnection)
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

    def save_splitter_state(self) -> None:
        if self.splitter_state_restored:  # ignore programmatic moves during initial layout
            data.save_game_splitter_state(bytes(self.splitter.saveState()))

    def load_game(self, game_id: str, state: GameState, images: dict[int, data.SceneImage] | None = None) -> None:
        self.game_id = game_id
        self.state = state
        self.images = dict(images or {})
        self.images_enabled = data.images_enabled()
        self.session_cost = 0.0
        self.last_save_name = data.save_name_for_title(state.world.title)
        self.cancel_pending_ai_calls()
        self.images_action.setChecked(self.images_enabled)
        self.apply_images_enabled()
        self.prompt_edit.clear()
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.refresh_ui()
        if not state.turns:
            self.request_turn('')  # the opening turn of a new game
        elif self.images_enabled and len(state.turns) not in self.images:
            self.request_image(len(state.turns))

    def cancel_pending_ai_calls(self) -> None:
        # In-flight generations keep running but their results are discarded
        # as their call numbers no longer match.
        self.turn_call = -1
        self.image_call = -1
        self.image_turn = -1
        self.input_stack.stop()

    def refresh_ui(self) -> None:
        self.render_story()
        if self.state is not None and self.state.turns:
            self.scroll_to_turn(len(self.state.turns))
        self.update_window_title()
        self.update_status()
        self.update_scene_panel()

    # Story display {{{

    def render_story(self) -> None:
        sv = self.story_view
        sv.clear()
        self.turn_positions = []
        state = self.state
        if state is None:
            return
        c = sv.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        if not state.turns:
            insert_html_block(c, f'<h2>{escape(state.world.title)}</h2>')
            insert_html_block(c, response_to_html(state.world.world_description, ContentType.markdown))
            insert_html_block(c, '<hr>')
            insert_html_block(c, f'<p><b>{_("Win condition")}</b></p>' + response_to_html(state.world.win_condition, ContentType.markdown))
            return
        insert_html_block(c, f'<h2>{escape(state.chapter_titles[state.current_chapter])}</h2>')
        for i, t in enumerate(state.turns):
            if t.chapter != state.current_chapter:
                continue
            if self.turn_positions:
                insert_html_block(c, '<hr>')
            self.turn_positions.append((c.position(), i + 1))
            if t.player_input:
                insert_html_block(c, f'<p><i>➤ {escape(t.player_input)}</i></p>')
            insert_html_block(c, response_to_html(t.turn.narrative, ContentType.markdown))
        insert_html_block(c, '<hr>')
        last = state.turns[-1].turn
        if last.outcome is GameOutcome.victory:
            insert_html_block(c, '<p><b>' + _('You have achieved victory!') + '</b></p>')
        elif last.outcome is GameOutcome.defeat:
            insert_html_block(c, '<p><b>' + _('You have been defeated!') + '</b></p>')
        if last.quick_actions:
            # each action in its own paragraph with a top margin, giving
            # enough space between the links to click them comfortably
            items = ''.join(
                f'<p style="margin-top: 8px; margin-left: 16px"><a href="{QUICK_ACTION_SCHEME}:{i}">{escape(a)}</a></p>'
                for i, a in enumerate(last.quick_actions)
            )
            insert_html_block(c, f'<h4>{_("Quick actions")}</h4>' + items)

    def quick_action(self, action_number: int) -> str:
        # The text of the zero based action_number quick action of the last
        # turn, empty when there is no such action.
        if self.state is None or not self.state.turns:
            return ''
        actions = self.state.turns[-1].turn.quick_actions
        return actions[action_number] if 0 <= action_number < len(actions) else ''

    def activate_quick_action(self, action_number: int) -> None:
        # Put the quick action into the prompt box, submitting it when it is
        # already there, so that activating an action twice plays it.
        action = self.quick_action(action_number)
        if not action:
            return
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
        if action := self.quick_action(action_number):
            tip = f'<p>{escape(action)}'
            if action_number < MAX_QUICK_ACTION_SHORTCUTS:
                tip += '<br>' + _('Shortcut: {}').format(f'Ctrl+{action_number + 1}')
            QToolTip.showText(QCursor.pos(), tip, self.story_view)
        else:
            QToolTip.hideText()

    def scroll_to_turn(self, turn_number: int) -> None:
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
        # 0 when no turns are displayed. That is the turn at the top of the
        # story view, except when the view is scrolled to the end: the last
        # turn is usually too short to reach the top of the view, but it is
        # what the player is reading.
        if not self.turn_positions:
            return 0
        vsb = self.story_view.verticalScrollBar()
        if vsb is None or vsb.value() >= vsb.maximum():
            return self.turn_positions[-1][1]
        p = self.story_view.cursorForPosition(QPoint(5, 5)).position()
        ans = self.turn_positions[0][1]
        for pos, tn in self.turn_positions:
            if pos > p:
                break
            ans = tn
        return ans

    def on_story_scrolled(self) -> None:
        self.update_scene_panel()

    # }}}

    # Scene panel and status displays {{{

    def condition_html(self) -> str:
        state = self.state
        if state is None:
            return ''
        if state.victory_achieved:
            return '<p><b>' + _('You have achieved victory!') + '</b></p>'
        if state.defeat_achieved:
            return '<p><b>' + _('You have been defeated!') + '</b></p>'
        return f'<p><b>{_("Win condition")}</b></p>' + response_to_html(state.world.win_condition, ContentType.markdown)

    def update_scene_panel(self) -> None:
        state = self.state
        if state is None:
            return
        if not self.images_enabled:
            html = f'<h3>{escape(state.world.title)}</h3>'
            html += response_to_html(state.world.world_description, ContentType.markdown)
            html += '<hr>' + self.condition_html()
            if html != self.info_view.property('cyoa-html'):  # avoid losing the scroll position on every update
                self.info_view.setProperty('cyoa-html', html)
                self.info_view.setHtml(html)
            return
        tn = self.visible_turn_number()
        img = self.images.get(tn)
        if tn and tn == self.image_turn:
            placeholder = _('Generating a picture of this scene…')
        else:
            placeholder = _('No picture of this scene is available')
        self.scene_image.set_image(img.data if img else None, placeholder)
        self.condition_label.setText(self.condition_html())

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
        models: list[str] = []
        currency = ''
        total_cost = 0.0
        for t in state.turns:
            if t.model and t.model not in models:
                models.append(t.model)
            total_cost += t.cost
            currency = currency or t.currency
        for img in self.images.values():
            if img.model and img.model not in models:
                models.append(img.model)
            total_cost += img.cost
            currency = currency or img.currency
        if models:
            parts.append(_('Models: {}').format(', '.join(models)))
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
        self.input_stack.start()
        Thread(name='CYOATurn', daemon=True, target=self.do_turn, args=(snapshot, player_input, interesting_event, self.turn_call, plugin)).start()

    def do_turn(self, snapshot: GameState, player_input: str, interesting_event: bool, call_number: int, plugin: AIProvider) -> None:
        try:
            # the preferences overlay is thread local so must be entered here
            with data.cyoa_ai_settings():
                res = next_turn(snapshot, player_input, plugin, interesting_event=interesting_event)
            if sip.isdeleted(self):
                return
            self.turn_result_received.emit(call_number, snapshot, res)
        except RuntimeError:
            pass  # when self gets deleted between call to sip.isdeleted and next statement

    def on_turn_result(self, call_number: int, snapshot: GameState, res: StructuredOutputResult) -> None:
        if call_number != self.turn_call:
            return  # a stale result from a superseded or cancelled call
        self.turn_call = -1
        self.input_stack.stop()
        if res.exception is not None:
            error_dialog(
                self,
                _('Failed to generate the next turn'),
                _('The AI failed to continue the story: {}').format(res.exception),
                det_msg=res.error_details,
                show=True,
            )
            return
        was_over = self.state is not None and self.state.game_over
        self.state = snapshot
        self.session_cost += res.cost
        self.prompt_edit.clear()
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.autosave()
        self.refresh_ui()
        if self.images_enabled:
            self.request_image(len(snapshot.turns))
        if not was_over and snapshot.game_over:
            self.show_game_over()

    def show_game_over(self) -> None:
        state = self.state
        if state is None:
            return
        if state.victory_achieved:
            title = _('Victory!')
            msg = _('Congratulations, you have achieved the win condition and completed the adventure!')
        else:
            title = _('Defeat')
            msg = _('Alas, you have been defeated and the adventure has come to an end.')
        keep_playing = question_dialog(
            self,
            title,
            '<p>' + msg + '</p><p>' + _('Do you want to keep playing this adventure anyway, or return to the world creation screen?'),
            yes_text=_('&Keep playing'),
            no_text=_('&New world'),
        )
        if not keep_playing:
            self.game_abandoned.emit()

    # }}}

    # Scene image generation {{{

    def apply_images_enabled(self) -> None:
        self.scene_image.setVisible(self.images_enabled)
        self.condition_label.setVisible(self.images_enabled)
        self.info_view.setVisible(not self.images_enabled)
        self.update_scene_panel()

    def toggle_images(self) -> None:
        enabled = self.images_action.isChecked()
        if enabled and not data.is_ready('image'):
            if ConfigureImageAIDialog(self).exec() != Dialog.DialogCode.Accepted or not data.is_ready('image'):
                self.images_action.setChecked(False)
                return
        data.mark_image_skipped(not enabled)
        self.images_enabled = enabled
        if not enabled:
            # Discard any in-flight image generation, its result no longer
            # matches image_call when it arrives.
            self.image_call = -1
            self.image_turn = -1
        self.apply_images_enabled()
        state = self.state
        if enabled and state is not None and state.turns and len(state.turns) not in self.images:
            self.request_image(len(state.turns))

    def request_image(self, turn_number: int) -> None:
        state = self.state
        if state is None or not self.images_enabled or not 0 < turn_number <= len(state.turns):
            return
        plugin = data.plugin_for('image')
        if plugin is None:
            return
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
                    image = data.SceneImage(data=webp, cost=res.cost, currency=res.currency, provider=res.provider, model=res.model)
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
            self.status_bar.showMessage(_('Failed to generate a picture of the scene: {}').format(res.error), 10000)
        else:
            self.images[turn_number] = res.image
            self.session_cost += res.image.cost
            self.autosave()
        self.update_status()
        self.update_scene_panel()

    # }}}

    # Saving, loading and rewinding {{{

    def autosave(self) -> None:
        if not self.game_id or self.state is None:
            return
        try:
            data.save_game(self.game_id, self.state, self.images)
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
            data.save_game(name, self.state, self.images, base=data.saves_dir())
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
            state, images = data.load_game(d.save_name, base=data.saves_dir())
        except Exception as e:
            error_dialog(self, _('Failed to load game'), _('Failed to load the saved game "{0}": {1}').format(d.save_name, e), show=True)
            return
        self.cancel_pending_ai_calls()
        self.state = state
        self.images = images
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

    def jump_to_turn(self) -> None:
        state = self.state
        if state is None or len(state.turns) < 2:
            self.status_bar.showMessage(_('There are no other turns to jump to.'), 5000)
            return
        n = len(state.turns)
        num, ok = QInputDialog.getInt(self, _('Jump to turn'), _('Jump to turn number (1 to {}):').format(n), n, 1, n)
        if not ok or num == n:
            return
        if question_dialog(self, _('Are you sure?'), _('Jump to turn {}? All turns after it are discarded and any unsaved progress will be lost.').format(num)):
            self.rewind_to_turn(num)

    def exit_to_world_generation(self) -> None:
        if question_dialog(
            self,
            _('Are you sure?'),
            _('Leave this game and return to the world creation screen? Any unsaved progress will be lost. Use the Save button to keep this game.'),
        ):
            self.game_abandoned.emit()

    # }}}


if __name__ == '__main__':
    from calibre.ai.cyoa import CharacterState, GeneratedWorld, PlayerCharacter, StorySummary, StoryTurn, start_game
    from calibre.gui2 import Application

    class FakePlugin:
        # Plays canned turns so the widget can be exercised without an AI
        counter = count(start=1)

        def generate_structured_output(self, prompt: str, schema: type, instructions: str = '', use_model: str = '') -> StructuredOutputResult:
            import time

            time.sleep(1)
            n = next(self.counter)
            turn = StoryTurn(
                narrative=f'**Turn {n}**: The mist *swirls* around you as something stirs in the distance.\n\nYou must decide quickly.',
                quick_actions=(f'Look around (turn {n})', 'Call out', 'Run away'),
                scene_description='A foggy city street at night.',
                updated_summary=StorySummary(
                    world='A city lost in mist.',
                    major_events=tuple(f'event {i}' for i in range(1, n + 1)),
                    characters=(CharacterState('Ada', 'the player', 'alone so far'),),
                    current_situation='In the mist.',
                    upcoming_events=('The mist thickens.',),
                ),
                starts_new_chapter=n > 1 and (n % 4) == 0,
                chapter_title=f'Chapter of turn {n}' if n > 1 and (n % 4) == 0 else None,
                outcome=GameOutcome.victory if n == 6 else GameOutcome.undetermined,
            )
            return StructuredOutputResult(data=turn, raw='{}', cost=0.01 * n, currency='USD', provider='fake', model='fake-model')

    app = Application([])
    w = GameWidget()
    w.plugin_override = FakePlugin()
    pc = PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.')
    world = GeneratedWorld(title='Mist City', world_description='A city lost in *perpetual* mist.', characters=(pc,), win_condition='Escape the city.')
    # An empty game_id disables auto-saving, so the demo does not touch the
    # calibre config directory.
    w.load_game('', start_game('a foggy city', world, pc))
    w.game_abandoned.connect(lambda: print('game abandoned'))
    w.resize(1000, 720)
    w.show()
    app.exec()
    del w
    del app
