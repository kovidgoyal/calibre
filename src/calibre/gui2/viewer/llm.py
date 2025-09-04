# License: GPL v3 Copyright: 2025, Amir Tehrani and Kovid Goyal

import textwrap
from collections.abc import Iterator
from functools import lru_cache, partial
from itertools import count
from threading import Thread
from typing import NamedTuple

from qt.core import (
    QAbstractItemView,
    QDateTime,
    QDialog,
    QDialogButtonBox,
    QEvent,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLocale,
    QPalette,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    Qt,
    QTabWidget,
    QTextBrowser,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai import AICapabilities, ChatMessage, ChatMessageType, ChatResponse
from calibre.ai.config import ConfigureAI
from calibre.ai.prefs import plugin_for_purpose
from calibre.ai.utils import StreamedResponseAccumulator
from calibre.customize import AIProviderPlugin
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import Application, error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.viewer.config import vprefs
from calibre.gui2.viewer.highlights import HighlightColorCombo
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.short_uuid import uuid4


class Action(NamedTuple):
    name: str
    human_name: str
    prompt_text: str
    is_builtin: bool = True
    is_disabled: bool = False

    @property
    def as_custom_action_dict(self):
        return {'disabled': self.is_disabled, 'title': self.human_name, 'prompt_text': self.prompt_text}


@lru_cache(2)
def default_actions() -> tuple[Action, ...]:
    return (
        Action('summarize', _('Summarize'), 'Provide a concise summary of the selected text.'),
        Action('explain', _('Explain'), 'Explain the selected text in simple, easy-to-understand terms.'),
        Action('points', _('Key points'), 'Extract the key points from the selected text as a bulleted list.'),
        Action('define', _('Define'), 'Identify and define any technical or complex terms in the selected text.'),
        Action('grammar', _('Correct grammar'), 'Correct any grammatical errors in the selected text and provide the corrected version.'),
        Action('english', _('As English'), 'Translate the selected text into English.'),
    )


def current_actions(include_disabled=False):
    p = vprefs.get('llm_quick_actions') or {}
    dd = p.get('disabled_default_actions', ())
    for x in default_actions():
        x = x._replace(is_disabled=x.name in dd)
        if include_disabled or not x.is_disabled:
            yield x
    for title, c in p.get('custom_actions', {}).items():
        x = Action(f'custom-{title}', title, c['prompt_text'], is_builtin=False, is_disabled=c['disabled'])
        if include_disabled or x.is_disabled:
            yield x


class ConversationHistory:

    def __init__(self, conversation_text: str = ''):
        self.accumulator = StreamedResponseAccumulator()
        self.items: list[ChatMessage] = []
        self.conversation_text: str = conversation_text
        self.model_used = ''
        self.api_call_active = False
        self.current_response_completed = True
        self.cost = 0.
        self.response_count = 0
        self.currency = ''

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def append(self, x: ChatMessage) -> None:
        self.items.append(x)

    def copy(self, upto: int | None = None) -> 'ConversationHistory':
        ans = ConversationHistory(self.conversation_text)
        ans.model_used = self.model_used
        if upto is None:
            ans.items = list(self.items)
        else:
            ans.items = self.items[:upto]
        return ans

    def at(self, x: int) -> ChatMessage:
        return self.items[x]

    def new_api_call(self) -> None:
        self.accumulator = StreamedResponseAccumulator()
        self.current_response_completed = False
        self.api_call_active = True

    def finalize_response(self) -> None:
        self.current_response_completed = True
        self.api_call_active = False
        self.accumulator.finalize()
        self.items.extend(self.accumulator)
        self.response_count += 1
        if self.accumulator.metadata.has_metadata:
            self.model_used = self.accumulator.metadata.model
            self.cost += self.accumulator.metadata.cost
            self.currency = self.accumulator.metadata.currency


def format_llm_note(conversation: ConversationHistory, assistant_name: str) -> str:
    '''
    Formats a conversation history into a standardized, self-contained note entry.
    '''
    if not conversation:
        return ''

    main_response = ''
    for message in reversed(conversation):
        if message.from_assistant:
            main_response = message.query.strip()
            break

    if not main_response:
        return ''

    timestamp = QLocale.system().toString(QDateTime.currentDateTime(), QLocale.FormatType.LongFormat)
    header = f'--- {_("AI Assistant Note")} ({timestamp}) ---'

    record_lines = []
    for message in conversation:
        match message.type:
            case ChatMessageType.user:
                role = _('You')
            case ChatMessageType.assistant:
                role = assistant_name
            case _:
                continue
        content = message.query.strip()
        entry = f'{role}: {content}'
        record_lines.append(entry)

    record_body = '\n\n'.join(record_lines)
    record_header = f'--- {_("Conversation record")} ---'

    return (
        f'{header}\n\n{main_response}\n\n'
        f'------------------------------------\n\n'
        f'{record_header}\n\n{record_body}'
    )


class LLMPanel(QWidget):
    response_received = pyqtSignal(int, object)
    add_note_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.save_note_hostname = f'{uuid4().lower()}.calibre'
        self.configure_ai_hostname = f'{uuid4().lower()}.calibre'
        self.counter = count(start=1)

        self.conversation_history = ConversationHistory()
        self.latched_highlight_uuid = None
        self.latched_conversation_text = None
        self.current_api_call_number = 0
        self.session_cost = 0.0
        self.book_title = ''
        self.book_authors = ''
        self.update_ai_provider_plugin()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.quick_actions_group = QGroupBox(self)
        self.quick_actions_group.setTitle(_('Quick actions'))
        self.quick_actions_layout = QGridLayout(self.quick_actions_group)
        self.layout.addWidget(self.quick_actions_group)
        self.rebuild_actions_ui()

        custom_prompt_group = QGroupBox(self)
        custom_prompt_group.setTitle(_('Custom prompt'))
        custom_prompt_layout = QHBoxLayout(custom_prompt_group)
        self.custom_prompt_edit = QLineEdit(self)
        self.custom_prompt_edit.setPlaceholderText(_('Or, enter your own request...'))
        self.custom_prompt_button = QPushButton(_('&Send'), self)
        custom_prompt_layout.addWidget(self.custom_prompt_edit)
        custom_prompt_layout.addWidget(self.custom_prompt_button)
        self.layout.addWidget(custom_prompt_group)

        self.result_display = rd = QTextBrowser(self)
        rd.setOpenLinks(False)
        rd.setMinimumHeight(150)
        rd.anchorClicked.connect(self.on_chat_link_clicked)
        rd.setFrameShape(QFrame.Shape.NoFrame)
        rd.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(rd)

        response_actions_layout = QHBoxLayout()
        self.save_note_button = QPushButton(QIcon.ic('plus.png'), _('Save as note'), self)
        self.save_note_button.clicked.connect(self.save_as_note)

        self.new_chat_button = QPushButton(QIcon.ic('edit-clear.png'), _('New chat'), self)
        self.new_chat_button.setToolTip(_('Clear the current conversation history and start a new one'))
        self.new_chat_button.clicked.connect(self.start_new_conversation)
        self.new_chat_button.setEnabled(False)

        response_actions_layout.addWidget(self.save_note_button)
        response_actions_layout.addWidget(self.new_chat_button)
        response_actions_layout.addStretch()
        self.layout.addLayout(response_actions_layout)

        footer_layout = QHBoxLayout()
        self.settings_button = QPushButton(QIcon.ic('config'), _('Se&ttings'))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.api_usage_label = QLabel(_('API calls: 0 | Cost: ~$0.0000'))
        footer_layout.addWidget(self.settings_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.api_usage_label)
        self.layout.addLayout(footer_layout)

        self.custom_prompt_button.clicked.connect(self.run_custom_prompt)
        self.custom_prompt_edit.returnPressed.connect(self.run_custom_prompt)
        self.response_received.connect(self.on_response_from_ai, type=Qt.ConnectionType.QueuedConnection)
        self.settings_button.clicked.connect(self.show_settings)
        self.show_initial_message()

    def set_html(self, html: str) -> None:
        self.result_display.setHtml(html)
        self.result_display.document().setDocumentMargin(0)

    def update_book_metadata(self, metadata):
        self.book_title = metadata.get('title', '')
        authors = metadata.get('authors', [])
        self.book_authors = authors_to_string(authors)

    def rebuild_actions_ui(self):
        while self.quick_actions_layout.count():
            child = self.quick_actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        actions = sorted(current_actions(), key=lambda a: primary_sort_key(a.human_name))
        positions = [(i, j) for i in range(4) for j in range(2)]
        for i, action in enumerate(actions):
            if i >= len(positions):
                break
            button = QPushButton(action.human_name, self)
            button.setToolTip(action.prompt_text)
            button.clicked.connect(partial(self.activate_action, action))
            row, col = positions[i]
            self.quick_actions_layout.addWidget(button, row, col)

    def activate_action(self, action: Action) -> None:
        self.start_api_call(action.prompt_text)

    def show_settings(self):
        dialog = LLMSettingsDialog(self)
        dialog.actions_updated.connect(self.rebuild_actions_ui)
        dialog.exec()
        self.update_ai_provider_plugin()

    def update_ai_provider_plugin(self):
        self.ai_provider_plugin = plugin_for_purpose(AICapabilities.text_to_text)

    @property
    def is_ready_for_use(self) -> bool:
        p = self.ai_provider_plugin
        return p is not None and p.is_ready_for_use

    def show_initial_message(self):
        self.save_note_button.setEnabled(False)
        if not self.is_ready_for_use:
            self.show_html(f'<p><a href="http://{self.configure_ai_hostname}">{_("First, configure an AI provider")}')
        else:
            self.show_html('<p>' + _('Select text in the book to begin.'))

    def update_with_text(self, text, highlight_data=None):
        self.update_ai_provider_plugin()
        new_uuid = (highlight_data or {}).get('uuid')
        if not text and not new_uuid:
            if self.latched_conversation_text is not None or self.latched_highlight_uuid is not None:
                self.start_new_conversation()
            return

        start_new_convo = False
        if new_uuid != self.latched_highlight_uuid:
            start_new_convo = True
        elif new_uuid is None and text != self.latched_conversation_text:
            start_new_convo = True

        if start_new_convo:
            self.latched_highlight_uuid = new_uuid
            self.latched_conversation_text = text
            self.conversation_history = ConversationHistory()

            if text:
                self.show_html(f"<b>{_('Selected')}:</b><br><i>'{text[:200]}…'</i>")
            else:
                self.show_html(_('<b>Ready.</b> Ask a follow-up question.'))

        if self.latched_highlight_uuid:
            self.save_note_button.setToolTip(_("Append this response to the existing highlight's note"))
        else:
            self.save_note_button.setToolTip(_('Create a new highlight for the selected text and save this response as its note'))

    def run_custom_prompt(self):
        prompt = self.custom_prompt_edit.text().strip()
        if prompt:
            self.start_api_call(prompt)

    def start_new_conversation(self):
        self.conversation_history = ConversationHistory()
        self.latched_highlight_uuid = None
        self.latched_conversation_text = None

        self.new_chat_button.setEnabled(False)
        self.save_note_button.setEnabled(False)
        self.show_initial_message()

    @property
    def assistant_name(self) -> str:
        return self.ai_provider_plugin.human_readable_model_name(self.conversation_history.model_used) or _('Assistant')

    def render_conversation_html(self):
        html_output = ''
        pal = self.palette()
        assistant_color = pal.color(QPalette.ColorRole.Window).name()
        you_color = pal.color(QPalette.ColorRole.Base).name()
        def format_block(html: str, you_block: bool = False) -> str:
            return f'''<table width="100%" style="background-color: {you_color if you_block else assistant_color}" cellpadding="2">
                    <tr><td>{html}</td></tr></table>'''
        assistant = self.assistant_name
        for i, message in enumerate(self.conversation_history):
            content_for_display = message.for_display_to_human()
            if not content_for_display:
                continue
            if you_block := not message.from_assistant:
                header = f'{_("You")}'
            else:
                header = f'''<table width="100%" cellpadding="0" cellspacing="0"><tr><td><b><i>{assistant}\xa0</td>
                <td style="text-align: right"><a style="text-decoration: none"
                href="http://{self.save_note_hostname}/{i}" title="{_('Save this specific response as the note')}">{_(
                    'Save')}</a></td></tr></table>'''
            html_output += format_block(f'<div>{header}</div><div>{content_for_display}</div>', you_block)
        if self.conversation_history.api_call_active:
            content_for_display = ChatMessage(self.conversation_history.accumulator.all_content).for_display_to_human()
            header = f'''<div>{_('{} thinking…').format(assistant)}</div>'''
            html_output += format_block(f'<div>{header}</div><div>{content_for_display}</div>')
        return html_output

    def scroll_to_bottom(self) -> None:
        self.result_display.verticalScrollBar().setValue(self.result_display.verticalScrollBar().maximum())

    def start_api_call(self, action_prompt):
        if not self.is_ready_for_use:
            self.show_error(f"<b>{_('AI provider not configured.')}</b> <a href='http://configure-ai.com'>{_(
                'Configure AI provider')}</a>", is_critical=False)
            return
        if not self.latched_conversation_text:
            self.show_error(f"<b>{_('Error')}:</b> {_('No text is selected for this conversation.')}", is_critical=True)
            return

        if not self.conversation_history:
            self.conversation_history.conversation_text = self.latched_conversation_text
            context_header = ''
            if self.book_title:
                context_header = f'I am currently reading the book: {self.book_title}'
                if self.book_authors:
                    context_header += f' by {self.book_authors}'
                context_header += '.\n\n'
            context_header += f'I have selected the following text from this book:\n{self.latched_conversation_text}\n\n'
            self.conversation_history.append(ChatMessage(context_header, type=ChatMessageType.system))
        self.conversation_history.append(ChatMessage(action_prompt))
        self.set_html(self.render_conversation_html())
        self.set_all_inputs_enabled(False)
        self.scroll_to_bottom()

        self.current_api_call_number = next(self.counter)
        self.conversation_history.new_api_call()
        Thread(name='LLMAPICall', daemon=True, target=self.do_api_call, args=(
            self.conversation_history.copy(), self.current_api_call_number, self.ai_provider_plugin)).start()
        self.show_ai_conversation()

    def do_api_call(
        self, conversation_history: ConversationHistory, current_api_call_number: int, ai_plugin: AIProviderPlugin
    ) -> None:
        for res in ai_plugin.text_chat(conversation_history.items, conversation_history.model_used):
            self.response_received.emit(current_api_call_number, res)
        self.response_received.emit(current_api_call_number, None)

    def on_response_from_ai(self, current_api_call_number: int, r: ChatResponse | None) -> None:
        if current_api_call_number != self.current_api_call_number:
            return
        if r is None:
            self.conversation_history.finalize_response()
        else:
            self.conversation_history.accumulator.accumulate(r)
        self.show_ai_conversation()

    def show_ai_conversation(self):
        self.save_note_button.setEnabled(self.latched_conversation_text and self.conversation_history.response_count > 0)
        self.set_html(self.render_conversation_html())
        self.post_show()

    def show_html(self, html: str) -> None:
        self.save_note_button.setEnabled(False)
        self.set_html(html)
        self.post_show()

    def post_show(self):
        self.new_chat_button.setEnabled(True)
        self.set_all_inputs_enabled(True)
        self.custom_prompt_edit.clear()
        self.scroll_to_bottom()

    def show_error(self, html: str, is_critical: bool = False) -> None:
        self.show_html(f'<p style="color: {"red" if is_critical else "orange"}">{html}')

    def update_cost(self, usage_data):
        model_id = vprefs.get('llm_model_id', 'google/gemini-1.5-flash')
        prompt_tokens = usage_data.get('prompt_tokens', 0)
        completion_tokens = usage_data.get('completion_tokens', 0)
        prompt_cost = 0.0
        completion_cost = 0.0
        if not model_id.endswith(':free'):
            costs = MODEL_COSTS.get(model_id, MODEL_COSTS['default'])
            prompt_cost = (prompt_tokens / 1_000_000) * costs[0]
            completion_cost = (completion_tokens / 1_000_000) * costs[1]
        self.session_cost += prompt_cost + completion_cost
        self.api_usage_label.setText(f'{_("API calls")}: {self.current_api_call_number} | {_("Cost")}: ~${self.session_cost:.4f}')

    def save_as_note(self):
        if self.conversation_history.response_count > 0 and self.latched_conversation_text:
            payload = {
                'highlight': self.latched_highlight_uuid,
                'llm_note': format_llm_note(self.conversation_history, self.assistant_name),
            }
            self.add_note_requested.emit(payload)

    def save_specific_note(self, message_index):
        if not (0 <= message_index < len(self.conversation_history)):
            return
        if not self.conversation_history.at(message_index).from_assistant:
            return
        history_for_record = self.conversation_history.copy(message_index + 1)
        payload = {
            'highlight': self.latched_highlight_uuid,
            'llm_note': format_llm_note(history_for_record, self.assistant_name),
        }
        self.add_note_requested.emit(payload)

    def on_chat_link_clicked(self, qurl: QUrl):
        match qurl.host():
            case self.save_note_hostname:
                index = int(qurl.path().strip('/'))
                self.save_specific_note(index)
            case self.configure_ai_hostname:
                self.show_settings()

    def set_all_inputs_enabled(self, enabled):
        for i in range(self.quick_actions_layout.count()):
            widget = self.quick_actions_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(enabled)
        self.custom_prompt_edit.setEnabled(enabled)
        self.custom_prompt_button.setEnabled(enabled)


# Settings {{{

class ActionEditDialog(QDialog):
    def __init__(self, action: Action | None=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('Edit Quick action') if action else _('Add Quick action'))
        self.layout = QFormLayout(self)
        self.layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_edit = QLineEdit(self)
        self.prompt_edit = QPlainTextEdit(self)
        self.prompt_edit.setMinimumHeight(100)
        self.layout.addRow(_('Name:'), self.name_edit)
        self.layout.addRow(_('Prompt:'), self.prompt_edit)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        if action is not None:
            self.name_edit.setText(action.human_name)
            self.prompt_edit.setPlainText(action.prompt_text)
        self.name_edit.installEventFilter(self)
        self.prompt_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if obj is self.name_edit and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.prompt_edit.setFocus()
                return True
            if obj is self.prompt_edit and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self.accept()
                    return True
        return super().eventFilter(obj, event)

    def get_action(self) -> Action:
        title = self.name_edit.text().strip()
        return Action(f'custom-{title}', title, self.prompt_edit.toPlainText().strip())


class LLMSettingsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(550)
        self.layout = QVBoxLayout(self)
        api_model_layout = QFormLayout()
        api_model_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.highlight_color_combo = HighlightColorCombo(self)

        api_model_layout.addRow(_('&Highlight style:'), self.highlight_color_combo)
        self.layout.addLayout(api_model_layout)
        self.qa_gb = gb = QGroupBox(_('&Quick actions:'), self)
        self.layout.addWidget(gb)
        gb.l = l = QVBoxLayout(gb)
        self.actions_list = QListWidget(self)
        self.actions_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        l.addWidget(self.actions_list)
        actions_button_layout = QHBoxLayout()
        self.add_button = QPushButton(QIcon.ic('plus.png'), _('&Add'))
        self.edit_button = QPushButton(QIcon.ic('modified.png'), _('&Edit'))
        self.remove_button = QPushButton(QIcon.ic('minus.png'), _('&Remove'))
        actions_button_layout.addWidget(self.add_button)
        actions_button_layout.addWidget(self.edit_button)
        actions_button_layout.addWidget(self.remove_button)
        actions_button_layout.addStretch(100)
        l.addLayout(actions_button_layout)
        self.add_button.clicked.connect(self.add_action)
        self.edit_button.clicked.connect(self.edit_action)
        self.remove_button.clicked.connect(self.remove_action)
        self.actions_list.itemDoubleClicked.connect(self.edit_action)
        self.load_settings()
        self.actions_list.setFocus()

    def load_settings(self):
        if hsn := vprefs.get('llm_highlight_style'):
            self.highlight_color_combo.highlight_style_name = hsn
        self.load_actions_from_prefs()

    def action_as_item(self, ac: Action) -> QListWidgetItem:
        item = QListWidgetItem(ac.human_name, self.actions_list)
        item.setData(Qt.ItemDataRole.UserRole, ac)
        item.setCheckState(Qt.CheckState.Unchecked if ac.is_disabled else Qt.CheckState.Checked)
        item.setToolTip(textwrap.fill(ac.prompt_text))

    def load_actions_from_prefs(self):
        self.actions_list.clear()
        for ac in sorted(current_actions(include_disabled=True), key=lambda ac: primary_sort_key(ac.human_name)):
            self.action_as_item(ac)

    def add_action(self):
        dialog = ActionEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action = dialog.get_action()
            if action.human_name and action.prompt_text:
                self.action_as_item(action)

    def edit_action(self):
        item = self.actions_list.currentItem()
        if not item:
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        if action.is_builtin:
            return error_dialog(self, _('Cannot edit'), _(
                'Cannot edit builtin actions. Instead uncheck this action and create a new action with the same name.'), show=True)
        dialog = ActionEditDialog(action, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.get_action()
            if new_action.human_name and new_action.prompt_text:
                item.setText(new_action.human_name)
                item.setData(Qt.ItemDataRole.UserRole, new_action)

    def remove_action(self):
        item = self.actions_list.currentItem()
        if not item:
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        if action.is_builtin:
            return error_dialog(self, _('Cannot remove'), _(
                'Cannot remove builtin actions. Instead simply uncheck it to prevent it from showing up as a button.'), show=True)
        if item and confirm(
            _('Remove the {} action?').format(item.text()), 'confirm_remove_llm_action',
            confirm_msg=_('&Show this confirmation again'), parent=self,
        ):
            self.actions_list.takeItem(self.actions_list.row(item))

    def commit(self) -> bool:
        selected_internal_name = self.highlight_color_combo.currentData()
        vprefs.set('llm_highlight_style', selected_internal_name)
        disabled_defaults = []
        custom_actions = {}
        for i in range(self.actions_list.count()):
            item = self.actions_list.item(i)
            action:Action = item.data(Qt.ItemDataRole.UserRole)
            action = action._replace(is_disabled=item.checkState() == Qt.CheckState.Unchecked)
            if action.is_builtin:
                if action.is_disabled:
                    disabled_defaults.append(action.name)
            else:
                custom_actions[action.human_name] = action.as_custom_action_dict
        s = {}
        if disabled_defaults:
            s['disabled_default_actions'] = disabled_defaults
        if custom_actions:
            s['custom_actions'] = custom_actions
        vprefs.set('llm_quick_actions', s)
        return True


class LLMSettingsDialog(Dialog):
    actions_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(title=_('AI Settings'), name='llm-settings-dialog', prefs=vprefs, parent=parent)

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.tabs = tabs = QTabWidget(self)
        self.ai_config = ai = ConfigureAI(parent=self)
        tabs.addTab(ai, QIcon.ic('ai.png'), _('AI &Provider'))
        self.llm_config = llm = LLMSettingsWidget(self)
        tabs.addTab(llm, QIcon.ic('config.png'), _('Actions and &highlights'))
        tabs.setCurrentWidget(llm if self.ai_config.is_ready_for_use else ai)
        l.addWidget(tabs)
        l.addWidget(self.bb)

    def accept(self):
        if not self.ai_config.commit():
            self.tabs.setCurrentWidget(self.ai_config)
            return
        if not self.llm_config.commit():
            self.tabs.setCurrentWidget(self.llm_config)
            return
        self.actions_updated.emit()
        super().accept()
# }}}


def develop():
    app = Application([])
    # LLMSettingsDialog().exec()
    d = QDialog()
    l = QVBoxLayout(d)
    llm = LLMPanel(d)
    llm.update_with_text('developing')
    h = llm.conversation_history
    h.model_used = 'google/gemini-2.5-flash-image-preview:free'
    h.append(ChatMessage('Testing rendering of conversation widget'))
    h.append(ChatMessage('This is a reply from the LLM', type=ChatMessageType.assistant))
    h.append(ChatMessage('Another query from the user'))
    h.append(
        ChatMessage('''\
Nisi nec libero. Cras magna ipsum, scelerisque et, tempor eget, gravida nec, lacus.
Fusce eros nisi, ullamcorper blandit, ultricies eget, elementum eget, pede.
Phasellus id risus vitae nisl ullamcorper congue. Proin est.

Sed eleifend odio sed leo. Mauris tortor turpis, dignissim vel, ornare ac, ultricies quis, magna.
Phasellus lacinia, augue ac dictum tempor, nisi felis ornare magna, eu vehicula tellus enim eu neque.
Fusce est eros, sagittis eget, interdum a, ornare suscipit, massa. Sed vehicula elementum ligula.
Aliquam erat volutpat. Donec odio. Quisque nunc. Integer cursus feugiat magna.
Fusce ac elit ut elit aliquam suscipit. Duis leo est, interdum nec, varius in. ''', type=ChatMessageType.assistant))
    llm.show_ai_conversation()
    l.addWidget(llm)
    d.exec()
    del app


if __name__ == '__main__':
    develop()
