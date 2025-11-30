#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

import textwrap
from collections.abc import Iterator
from html import escape
from itertools import count
from threading import Thread
from typing import Any, NamedTuple

from qt.core import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDateTime,
    QDialog,
    QDialogButtonBox,
    QEvent,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLocale,
    QPlainTextEdit,
    QPushButton,
    QSize,
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
from calibre.ai.prefs import prefs as aiprefs
from calibre.ai.utils import ContentType, StreamedResponseAccumulator, response_to_html
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog, safe_open_url
from calibre.gui2.chat_widget import Button, ChatWidget, Header
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import ui_language_as_english
from calibre.utils.logging import ERROR, WARN
from calibre.utils.short_uuid import uuid4
from polyglot.binary import as_hex_unicode

prompt_sep = '\n\n------\n\n'
reasoning_icon = 'reports.png'


def for_display_to_human(self: ChatMessage, is_initial_query: bool = False, content_type: ContentType = ContentType.unknown) -> str:
    if self.type is ChatMessageType.system:
        return ''
    q = self.query
    if is_initial_query and (idx := q.find(prompt_sep)) > -1:
        q = q[:idx] + '\n\n' + q[idx + len(prompt_sep):]
    return response_to_html(q, content_type=content_type)


def show_reasoning(reasoning: str, parent: QWidget | None = None):
    d = QDialog(parent)
    l = QVBoxLayout(d)
    b = QTextBrowser(d)
    b.setPlainText(reasoning)
    l.addWidget(b)
    d.setWindowTitle(_('Reasoning used by AI'))
    d.setWindowIcon(QIcon.ic(reasoning_icon))
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, d)
    l.addWidget(bb)
    d.resize(600, 500)
    d.exec()


class ConversationHistory:

    def __init__(self):
        self.accumulator = StreamedResponseAccumulator()
        self.items: list[ChatMessage] = []
        self.model_used = ''
        self.api_call_active = False
        self.current_response_completed = True
        self.cost = 0.
        self.response_count = 0
        self.currency = ''

    def __iter__(self) -> Iterator[ChatMessage]:
        return iter(self.items)

    def reverse_iter(self) -> Iterator[ChatMessage]:
        return reversed(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def append(self, x: ChatMessage) -> None:
        self.items.append(x)

    def copy(self, upto: int | None = None) -> 'ConversationHistory':
        ans = ConversationHistory()
        ans.model_used = self.model_used
        if upto is None:
            ans.items = list(self.items)
        else:
            ans.items = self.items[:upto]
        return ans

    def only(self, message_index: int) -> 'ConversationHistory':
        ans = self.copy(message_index + 1)
        ans.items = [ans.items[-1]]
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

    def format_llm_note(self, assistant_name: str, title: str = '') -> str:
        '''
        Formats a conversation history into a standardized, self-contained note entry.
        '''
        if not self:
            return ''

        main_response = ''
        for message in self.reverse_iter():
            if message.from_assistant:
                main_response = message.query.strip()
                break

        if not main_response:
            return ''

        timestamp = QLocale.system().toString(QDateTime.currentDateTime(), QLocale.FormatType.ShortFormat)
        sep = '―――'
        title = title or _('AI Assistant Note')
        header = f'{sep} {title} ({timestamp}) {sep}'
        if len(self) == 1:
            return f'{header}\n\n{main_response}'

        record_lines = []
        for message in self:
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
        record_header = f'{sep} {_("Conversation record")} {sep}'

        return (
            f'{header}\n\n{main_response}\n\n'
            f'{record_header}\n\n{record_body}'
        )


class ConverseWidget(QWidget):
    response_received = pyqtSignal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.counter = count(start=1)
        self.hid = hid = uuid4().lower()
        self.configure_ai_hostname = f'{hid}.config.calibre'
        self.copy_hostname = f'{hid}.copy.calibre'
        self.quick_action_hostname = f'{hid}.quick.calibre'
        self.reasoning_hostname = f'{hid}.reasoning.calibre'

        self.current_api_call_number = 0
        self.session_cost = 0.0
        self.session_cost_currency = ''
        self.update_ai_provider_plugin()
        self.clear_current_conversation()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.result_display = rd = ChatWidget(self, _('Type a question to the AI'))
        rd.link_clicked.connect(self.on_chat_link_clicked)
        rd.input_from_user.connect(self.run_custom_prompt)
        self.layout.addWidget(rd)

        self.response_actions_layout = QHBoxLayout()
        self.response_buttons = {}
        self.add_buttons()
        self.response_actions_layout.addStretch()
        self.layout.addLayout(self.response_actions_layout)

        footer_layout = QHBoxLayout()
        self.settings_button = QPushButton(QIcon.ic('config'), _('Se&ttings'))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.api_usage_label = QLabel('')
        footer_layout.addWidget(self.settings_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.api_usage_label)
        self.layout.addLayout(footer_layout)

        self.response_received.connect(self.on_response_from_ai, type=Qt.ConnectionType.QueuedConnection)
        self.settings_button.clicked.connect(self.show_settings)
        self.show_initial_message()
        self.update_cost()

    def language_instruction(self):
        lang = ui_language_as_english()
        return f'If you can speak in {lang}, then respond in {lang}.'

    def quick_actions_as_html(self, actions) -> str:
        actions = sorted(actions, key=lambda a: primary_sort_key(a.human_name))
        if not actions:
            return ''
        ans = []
        for action in actions:
            hn = action.human_name.replace(' ', '\xa0')
            ans.append(f'''<a title="{self.prompt_text_for_action(action)}"
            href="http://{self.quick_action_hostname}/{as_hex_unicode(action.name)}"
            style="text-decoration: none">{hn}</a>''')
        links = '\xa0\xa0\xa0 '.join(ans)
        return f'<h3>{_("Quick actions")}</h3> {links}'

    def show_settings(self):
        self.settings_dialog().exec()
        self.update_ai_provider_plugin()
        self.update_ui_state()

    def update_ai_provider_plugin(self):
        self.ai_provider_plugin = plugin_for_purpose(AICapabilities.text_to_text)

    @property
    def is_ready_for_use(self) -> bool:
        p = self.ai_provider_plugin
        return p is not None and p.is_ready_for_use

    def show_initial_message(self):
        if self.is_ready_for_use:
            msg = self.ready_message()
        else:
            msg = f'<a href="http://{self.configure_ai_hostname}">{_("First, configure an AI provider")}'
        self.result_display.show_message(msg)

    def run_custom_prompt(self, prompt: str) -> None:
        if prompt := prompt.strip():
            self.start_api_call(prompt)

    @property
    def assistant_name(self) -> str:
        return self.ai_provider_plugin.human_readable_model_name(self.conversation_history.model_used) or _('Assistant')

    def show_ai_conversation(self):
        self.result_display.clear()
        assistant = self.assistant_name
        is_initial_query = True
        content_type = self.conversation_history.accumulator.content_type
        for i, message in enumerate(self.conversation_history):
            content_for_display = for_display_to_human(message, is_initial_query, content_type)
            if message.type is ChatMessageType.user:
                is_initial_query = False
            if not content_for_display:
                continue
            header = Header()
            is_response = False
            if message.from_assistant:
                is_response = True
                buttons = tuple(self.per_response_buttons(i, message))
                buttons += (
                    Button('edit-copy.png', f'http://{self.copy_hostname}/{i}', _(
                        'Copy this specific response to the clipboard')),
                )
                if message.reasoning:
                    buttons += (Button(reasoning_icon, f'http://{self.reasoning_hostname}/{i}', _(
                        'Show the reasoning behind this response from the AI')),)
                header = Header(assistant, buttons)
            self.result_display.add_block(content_for_display, header, is_response)
        if self.conversation_history.api_call_active:
            a = self.conversation_history.accumulator
            has_content = bool(a.all_content)
            content_for_display = for_display_to_human(ChatMessage(a.all_content or a.all_reasoning))
            activity = _('answering') if has_content else _('thinking')
            if not has_content:
                content_for_display = '<i>' + content_for_display + '</i>'
            self.result_display.add_block(
                content_for_display, Header(_('{assistant} {activity}…').format(
                    assistant=assistant, activity=activity)), is_response=True)
        self.result_display.re_render()
        self.scroll_to_bottom()

    def get_language_instruction(self) -> str:
        if aiprefs['llm_localized_results'] != 'always':
            return ''
        return self.language_instruction()

    def scroll_to_bottom(self) -> None:
        self.result_display.scroll_to_bottom()

    def start_api_call(self, action_prompt: str, **kwargs: Any) -> None:
        if not self.is_ready_for_use:
            self.show_error(f'''<b>{_('AI provider not configured.')}</b> <a href="http://{self.configure_ai_hostname}">{_(
                'Configure AI provider')}</a>''', is_critical=False)
            return
        if err := self.ready_to_start_api_call():
            self.show_error(f"<b>{_('Error')}:</b> {err}", is_critical=True)
            return

        if self.conversation_history:
            self.conversation_history.append(ChatMessage(action_prompt))
        else:
            for msg in self.create_initial_messages(action_prompt, **kwargs):
                self.conversation_history.append(msg)
        self.current_api_call_number = next(self.counter)
        self.conversation_history.new_api_call()
        Thread(name='LLMAPICall', daemon=True, target=self.do_api_call, args=(
            self.conversation_history.copy(), self.current_api_call_number, self.ai_provider_plugin)).start()
        self.update_ui_state()

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
            self.update_cost()
        elif r.exception is not None:
            self.show_error(f'''{_('Talking to AI failed with error:')} {escape(str(r.exception))}''', details=r.error_details, is_critical=True)
        else:
            self.conversation_history.accumulator.accumulate(r)
        self.update_ui_state()

    def show_error(self, html: str, is_critical: bool = False, details: str = '') -> None:
        self.clear_current_conversation()
        level = ERROR if is_critical else WARN
        self.result_display.show_message(html, details, level)

    def clear_current_conversation(self) -> None:
        self.conversation_history = ConversationHistory()

    def update_ui_state(self) -> None:
        if self.conversation_history:
            self.show_ai_conversation()
        elif msg := self.choose_action_message():
            self.result_display.show_message(msg)
        else:
            self.show_initial_message()
        has_responses = self.conversation_history.response_count > 0
        for b in self.response_buttons.values():
            b.setEnabled(has_responses)

    def update_cost(self):
        h = self.conversation_history
        if self.session_cost_currency != h.currency:
            self.session_cost = 0
            self.session_cost_currency = h.currency
        if self.session_cost_currency:
            self.session_cost += h.cost
            cost = _('free')
            if self.session_cost:
                cost = f'{self.session_cost:.6f}'.rstrip('0').rstrip('.') + f' {self.session_cost_currency}'
            self.api_usage_label.setText(f'{_("Queries:")} {self.current_api_call_number} @ {cost}')
        else:
            self.api_usage_label.setText(f'{_("Queries:")} {self.current_api_call_number}')

    def get_conversation_history_for_specific_response(self, message_index: int) -> ConversationHistory | None:
        if not (0 <= message_index < len(self.conversation_history)):
            return None
        ans = self.conversation_history.at(message_index)
        if not ans.from_assistant:
            return None
        return self.conversation_history.only(message_index)

    def show_reasoning(self, message_index: int) -> None:
        h = self.get_conversation_history_for_specific_response(message_index)
        m = h.at(len(h)-1)
        if m.reasoning:
            show_reasoning(m.reasoning, self)

    def copy_specific_note(self, message_index: int) -> None:
        history_for_record = self.get_conversation_history_for_specific_response(message_index)
        text = history_for_record.format_llm_note(self.assistant_name, self.NOTE_TITLE)
        if text:
            QApplication.instance().clipboard().setText(text)

    def copy_to_clipboard(self) -> None:
        text = self.conversation_history.format_llm_note(self.assistant_name, self.NOTE_TITLE)
        if text:
            QApplication.instance().clipboard().setText(text)

    def on_chat_link_clicked(self, qurl: QUrl):
        if qurl.scheme() not in ('http', 'https'):
            return
        match qurl.host():
            case self.copy_hostname:
                index = int(qurl.path().strip('/'))
                self.copy_specific_note(index)
                return
            case self.reasoning_hostname:
                index = int(qurl.path().strip('/'))
                self.show_reasoning(index)
                return
            case self.configure_ai_hostname:
                self.show_settings()
                return
        if self.handle_chat_link(qurl):
            return
        safe_open_url(qurl)

    def set_all_inputs_enabled(self, enabled):
        for i in range(self.quick_actions_layout.count()):
            widget = self.quick_actions_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(enabled)
        self.result_display.set_input_enabled(enabled)

    def add_button(self, icon: str, text: str, tooltip: str) -> QPushButton:
        b = QPushButton(QIcon.ic(icon), text, self)
        b.setToolTip(tooltip)
        b.setEnabled(False)
        self.response_buttons[text] = b
        self.response_actions_layout.addWidget(b)
        return b

    # Subclass API {{{
    NOTE_TITLE = ''

    def add_buttons(self) -> None:
        self.add_button('edit-clear.png', _('&New chat'), _('Start a new conversation')).clicked.connect(
            self.start_new_conversation)
        self.add_button('edit-copy.png', _('&Copy'), _('Copy this conversation to the clipboard')).clicked.connect(
            self.copy_to_clipboard)

    def per_response_buttons(self, msgnum: int, msg: ChatMessage) -> Iterator[Button]:
        if False:
            yield Button()

    def settings_dialog(self) -> QDialog:
        raise NotImplementedError('implement in subclass')

    def handle_chat_link(self, qurl: QUrl) -> bool:
        raise NotImplementedError('implement in subclass')

    def create_initial_messages(self, action_prompt: str, **kwargs: Any) -> Iterator[ChatMessage]:
        raise NotImplementedError('implement in sub class')

    def ready_message(self) -> str:
        return _('Select text in the book to begin.')

    def choose_action_message(self) -> str:
        raise NotImplementedError('implement in sub class')

    def prompt_text_for_action(self, action) -> str:
        raise NotImplementedError('implement in sub class')

    def start_new_conversation(self) -> None:
        self.clear_current_conversation()
        self.update_ui_state()

    def ready_to_start_api_call(self) -> str:
        return ''
    # }}}


class ActionData(NamedTuple):
    name: str
    human_name: str
    prompt_template: str
    is_builtin: bool = True
    is_disabled: bool = False

    @property
    def as_custom_action_dict(self) -> dict[str, Any]:
        return {'disabled': self.is_disabled, 'title': self.human_name, 'prompt_template': self.prompt_template}

    @classmethod
    def unserialize(cls, p: dict[str, Any], default_actions: tuple['ActionData', ...], include_disabled=False) -> Iterator['ActionData']:
        dd = p.get('disabled_default_actions', ())
        for x in default_actions:
            x = x._replace(is_disabled=x.name in dd)
            if include_disabled or not x.is_disabled:
                yield x
        for title, c in p.get('custom_actions', {}).items():
            x = cls(f'custom-{title}', title, c['prompt_template'], is_builtin=False, is_disabled=c['disabled'])
            if include_disabled or not x.is_disabled:
                yield x


class ActionEditDialog(QDialog):

    def __init__(self, help_text: str, action: ActionData | None=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('Edit Quick action') if action else _('Add Quick action'))
        self.layout = QFormLayout(self)
        self.layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name_edit = QLineEdit(self)
        self.prompt_edit = QPlainTextEdit(self)
        self.prompt_edit.setMinimumHeight(100)
        self.layout.addRow(_('Name:'), self.name_edit)
        self.layout.addRow(_('Prompt:'), self.prompt_edit)
        self.help_label = la = QLabel(help_text)
        la.setWordWrap(True)
        self.layout.addRow(la)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        if action is not None:
            self.name_edit.setText(action.human_name)
            self.prompt_edit.setPlainText(action.prompt_template)
        self.name_edit.installEventFilter(self)
        self.prompt_edit.installEventFilter(self)

    def sizeHint(self) -> QSize:
        ans = super().sizeHint()
        ans.setWidth(max(500, ans.width()))
        return ans

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

    def get_action(self) -> ActionData:
        title = self.name_edit.text().strip()
        return ActionData(f'custom-{title}', title, self.prompt_edit.toPlainText().strip(), is_builtin=False)

    def accept(self) -> None:
        ac = self.get_action()
        if not ac.human_name:
            return error_dialog(self, _('No name specified'), _('You must specify a name for the Quick action'), show=True)
        if not ac.prompt_template:
            return error_dialog(self, _('No prompt specified'), _('You must specify a prompt for the Quick action'), show=True)
        super().accept()


class LocalisedResults(QCheckBox):

    def __init__(self):
        super().__init__(_('Ask the AI to respond in the current language'))
        self.setToolTip('<p>' + _(
            'Ask the AI to respond in the current calibre user interface language. Note that how well'
            ' this works depends on the individual model being used. Different models support'
            ' different languages.'))

    def load_settings(self):
        self.setChecked(aiprefs['llm_localized_results'] == 'always')

    def commit(self) -> bool:
        aiprefs['llm_localized_results'] = 'always' if self.isChecked() else 'never'
        return True


class LLMActionsSettingsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(550)
        self.layout = QVBoxLayout(self)
        api_model_layout = QFormLayout()
        api_model_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.custom_widgets = []
        for (title, w) in self.create_custom_widgets():
            if title:
                api_model_layout.addRow(title, w)
            else:
                api_model_layout.addRow(w)
            self.custom_widgets.append(w)
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
        for w in self.custom_widgets:
            w.load_settings()
        self.load_actions_from_prefs()

    def action_as_item(self, ac: ActionData) -> QListWidgetItem:
        item = QListWidgetItem(ac.human_name, self.actions_list)
        item.setData(Qt.ItemDataRole.UserRole, ac)
        item.setCheckState(Qt.CheckState.Unchecked if ac.is_disabled else Qt.CheckState.Checked)
        item.setToolTip(textwrap.fill(ac.prompt_template))

    def load_actions_from_prefs(self):
        self.actions_list.clear()
        for ac in sorted(self.get_actions_from_prefs(), key=lambda ac: primary_sort_key(ac.human_name)):
            self.action_as_item(ac)

    def add_action(self):
        dialog = ActionEditDialog(self.action_edit_help_text, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action = dialog.get_action()
            if action.human_name and action.prompt_template:
                self.action_as_item(action)

    def edit_action(self):
        item = self.actions_list.currentItem()
        if not item:
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        if action.is_builtin:
            return error_dialog(self, _('Cannot edit'), _(
                'Cannot edit builtin actions. Instead uncheck this action and create a new action with the same name.'), show=True)
        dialog = ActionEditDialog(self.action_edit_help_text, action, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.get_action()
            if new_action.human_name and new_action.prompt_template:
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
        for w in self.custom_widgets:
            if not w.commit():
                return False
        disabled_defaults = []
        custom_actions = {}
        for i in range(self.actions_list.count()):
            item = self.actions_list.item(i)
            action:ActionData = item.data(Qt.ItemDataRole.UserRole)
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
        self.set_actions_in_prefs(s)
        return True

    # Subclass API {{{
    action_edit_help_text = ''
    def get_actions_from_prefs(self) -> Iterator[ActionData]:
        raise NotImplementedError('implement in sub class')

    def set_actions_in_prefs(self, s: dict[str, Any]) -> None:
        raise NotImplementedError('implement in sub class')

    def create_custom_widgets(self) -> Iterator[str, QWidget]:
        raise NotImplementedError('implement in sub class')
    # }}}


class LLMSettingsDialogBase(Dialog):

    def __init__(self, name, prefs, title='', parent=None):
        super().__init__(title=title or _('AI Settings'), name=name, prefs=prefs, parent=parent)

    def custom_tabs(self) -> Iterator[str, str, QWidget]:
        if False:
            yield 'icon', 'title', QWidget()

    def setup_ui(self):
        l = QVBoxLayout(self)
        self.tabs = tabs = QTabWidget(self)
        self.ai_config = ai = ConfigureAI(parent=self)
        tabs.addTab(ai, QIcon.ic('ai.png'), _('AI &Provider'))
        for (icon, title, widget) in self.custom_tabs():
            tabs.addTab(widget, QIcon.ic(icon), title)
        tabs.setCurrentIndex(1 if self.ai_config.is_ready_for_use else 0)
        l.addWidget(tabs)
        l.addWidget(self.bb)

    def accept(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not w.commit():
                self.tabs.setCurrentWidget(w)
                return
        super().accept()
