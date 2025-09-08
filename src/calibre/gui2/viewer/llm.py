# License: GPL v3 Copyright: 2025, Amir Tehrani and Kovid Goyal

import string
import textwrap
from collections.abc import Callable, Iterator
from functools import lru_cache
from html import escape
from itertools import count
from threading import Thread
from typing import Any, NamedTuple

from qt.core import (
    QAbstractItemView,
    QApplication,
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
from calibre.ai.utils import StreamedResponseAccumulator, response_to_html
from calibre.customize import AIProviderPlugin
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import Application, error_dialog
from calibre.gui2.chat_widget import Button, ChatWidget, Header
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.viewer.config import vprefs
from calibre.gui2.viewer.highlights import HighlightColorCombo
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import calibre_langcode_to_name, canonicalize_lang, get_lang
from calibre.utils.logging import ERROR, WARN
from calibre.utils.short_uuid import uuid4
from polyglot.binary import as_hex_unicode, from_hex_unicode

prompt_sep = '\n\n------\n\n'
reasoning_icon = 'reports.png'


def for_display_to_human(self: ChatMessage, is_initial_query: bool = False) -> str:
    if self.type is ChatMessageType.system:
        return ''
    q = self.query
    if is_initial_query and (idx := q.find(prompt_sep)) > -1:
        q = q[:idx] + '\n\n' + q[idx + len(prompt_sep):]
    return response_to_html(q)


class Action(NamedTuple):
    name: str
    human_name: str
    prompt_template: str
    is_builtin: bool = True
    is_disabled: bool = False

    @property
    def as_custom_action_dict(self) -> dict[str, Any]:
        return {'disabled': self.is_disabled, 'title': self.human_name, 'prompt_template': self.prompt_template}

    @property
    def uses_selected_text(self) -> bool:
        for _, fname, _, _ in string.Formatter().parse(self.prompt_template):
            if fname == 'selected':
                return True
        return False

    def prompt_text(self, selected_text: str = '') -> str:
        probably_has_multiple_words = len(selected_text) > 20 or ' ' in selected_text
        pt = self.prompt_template
        what = 'Text to analyze: ' if probably_has_multiple_words else 'Word to analyze: '
        if not probably_has_multiple_words:
            match self.name:
                case 'explain':
                    pt = 'Explain the meaning, etymology and common usages of the following word in simple, easy to understand language. {selected}'
                case 'define':
                    pt = 'Explain the meaning and common usages of the following word. {selected}'
                case 'translate':
                    pt = 'Translate the following word into the language {language}. {selected}'

        selected_text = (prompt_sep + what + selected_text) if selected_text else ''
        return pt.format(
            selected=selected_text,
            language=calibre_langcode_to_name(canonicalize_lang(get_lang()) or 'English', localize=False),
        ).strip()


@lru_cache(2)
def default_actions() -> tuple[Action, ...]:
    return (
        Action('explain', _('Explain'), 'Explain the following text in simple, easy to understand language. {selected}'),
        Action('define', _('Define'), 'Identify and define any technical or complex terms in the following text. {selected}'),
        Action('summarize', _('Summarize'), 'Provide a concise summary of the following text. {selected}'),
        Action('points', _('Key points'), 'Extract the key points from the following text as a bulleted list. {selected}'),
        Action('grammar', _('Fix grammar'), 'Correct any grammatical errors in the following text and provide the corrected version. {selected}'),
        Action('translate', _('Translate'), 'Translate the following text into the language {language}. {selected}'),
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
        if include_disabled or not x.is_disabled:
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

    def reverse_iter(self) -> Iterator[ChatMessage]:
        return reversed(self.items)

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


def format_llm_note(conversation: ConversationHistory, assistant_name: str) -> str:
    '''
    Formats a conversation history into a standardized, self-contained note entry.
    '''
    if not conversation:
        return ''

    main_response = ''
    for message in conversation.reverse_iter():
        if message.from_assistant:
            main_response = message.query.strip()
            break

    if not main_response:
        return ''

    timestamp = QLocale.system().toString(QDateTime.currentDateTime(), QLocale.FormatType.ShortFormat)
    sep = '―――'
    header = f'{sep} {_("AI Assistant Note")} ({timestamp}) {sep}'
    if len(conversation) == 1:
        return f'{header}\n\n{main_response}'

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
    record_header = f'{sep} {_("Conversation record")} {sep}'

    return (
        f'{header}\n\n{main_response}\n\n'
        f'{record_header}\n\n{record_body}'
    )


class LLMPanel(QWidget):
    response_received = pyqtSignal(int, object)
    add_note_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        hid = uuid4().lower()
        self.save_note_hostname = f'{hid}.save.calibre'
        self.configure_ai_hostname = f'{hid}.config.calibre'
        self.copy_hostname = f'{hid}.copy.calibre'
        self.quick_action_hostname = f'{hid}.quick.calibre'
        self.reasoning_hostname = f'{hid}.reasoning.calibre'
        self.counter = count(start=1)

        self.latched_conversation_text = ''
        self.current_selected_text = ''
        self.current_api_call_number = 0
        self.session_cost = 0.0
        self.session_cost_currency = ''
        self.book_title = ''
        self.book_authors = ''
        self.update_ai_provider_plugin()
        self.clear_current_conversation()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.result_display = rd = ChatWidget(self, _('Type a question to the AI'))
        rd.link_clicked.connect(self.on_chat_link_clicked)
        rd.input_from_user.connect(self.run_custom_prompt)
        self.layout.addWidget(rd)

        response_actions_layout = QHBoxLayout()
        self.response_buttons = {}

        def button(action: Callable[[], None], icon: str, text: str, tooltip: str) -> QPushButton:
            b = QPushButton(QIcon.ic(icon), text, self)
            b.setToolTip(tooltip)
            b.setEnabled(False)
            self.response_buttons[action] = b
            b.clicked.connect(action)
            response_actions_layout.addWidget(b)
            return b

        button(self.save_as_note, 'save.png', _('&Save as note'), _('Save this conversation as a note on the current highlight'))
        button(self.start_new_conversation, 'edit-clear.png', _('&New chat'), _('Start a new conversation'))
        button(self.copy_to_clipboard, 'edit-copy.png', _('&Copy'), _('Copy this conversation to the clipboard'))

        response_actions_layout.addStretch()
        self.layout.addLayout(response_actions_layout)

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

    def update_book_metadata(self, metadata):
        self.book_title = metadata.get('title', '')
        authors = metadata.get('authors', [])
        self.book_authors = authors_to_string(authors)

    @property
    def quick_actions_as_html(self) -> str:
        actions = sorted(current_actions(), key=lambda a: primary_sort_key(a.human_name))
        if not actions:
            return ''
        ans = []
        for action in actions:
            hn = action.human_name.replace(' ', '\xa0')
            ans.append(f'''<a title="{action.prompt_text()}"
            href="http://{self.quick_action_hostname}/{as_hex_unicode(action.name)}"
            style="text-decoration: none">{hn}</a>''')
        links = '\xa0\xa0\xa0 '.join(ans)
        return f'<h3>{_("Quick actions")}</h3> {links}'

    def activate_action(self, action: Action) -> None:
        self.start_api_call(action.prompt_text(self.latched_conversation_text), action.uses_selected_text)

    def show_settings(self):
        LLMSettingsDialog(self).exec()
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
            msg = _('Select text in the book to begin.')
        else:
            msg = f'<a href="http://{self.configure_ai_hostname}">{_("First, configure an AI provider")}'
        self.result_display.show_message(msg)

    def update_with_text(self, text: str) -> None:
        self.current_selected_text = text
        self.update_ai_provider_plugin()
        if not text:
            if self.conversation_history:
                # preserve the current
                return
            self.latched_conversation_text = ''
            self.update_ui_state()
            return
        start_new_convo = False
        if text != self.latched_conversation_text:
            start_new_convo = True

        if start_new_convo:
            self.latched_conversation_text = text
            self.clear_current_conversation()
        self.update_ui_state()

    def run_custom_prompt(self, prompt: str) -> None:
        if prompt := prompt.strip():
            self.start_api_call(prompt)

    def start_new_conversation(self):
        self.clear_current_conversation()
        self.latched_conversation_text = ''
        self.update_ui_state()

    @property
    def assistant_name(self) -> str:
        return self.ai_provider_plugin.human_readable_model_name(self.conversation_history.model_used) or _('Assistant')

    def show_ai_conversation(self):
        self.result_display.clear()
        assistant = self.assistant_name
        is_initial_query = True
        for i, message in enumerate(self.conversation_history):
            content_for_display = for_display_to_human(message, is_initial_query)
            if message.type is ChatMessageType.user:
                is_initial_query = False
            if not content_for_display:
                continue
            header = Header()
            is_response = False
            if message.from_assistant:
                is_response = True
                buttons = (
                    Button('save.png', f'http://{self.save_note_hostname}/{i}', _(
                        'Save this specific response as the note')),
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

    def scroll_to_bottom(self) -> None:
        self.result_display.scroll_to_bottom()

    def create_initial_messages(self, action_prompt: str, selected_text: str) -> Iterator[ChatMessage]:
        if self.book_title:
            context_header = f'I am currently reading the book: {self.book_title}'
            if self.book_authors:
                context_header += f' by {self.book_authors}'
            if selected_text:
                context_header += '. I have some questions about content from this book.'
            else:
                context_header += '. I have some questions about this book.'
            yield ChatMessage(context_header, type=ChatMessageType.system)
        yield ChatMessage(action_prompt)

    def start_api_call(self, action_prompt: str, uses_selected_text: bool = False):
        if not self.is_ready_for_use:
            self.show_error(f'''<b>{_('AI provider not configured.')}</b> <a href="http://configure-ai.com">{_(
                'Configure AI provider')}</a>''', is_critical=False)
            return
        if not self.latched_conversation_text:
            self.show_error(f"<b>{_('Error')}:</b> {_('No text is selected for this conversation.')}", is_critical=True)
            return

        if self.conversation_history:
            self.conversation_history.append(ChatMessage(action_prompt))
        else:
            self.conversation_history.conversation_text = self.latched_conversation_text
            for msg in self.create_initial_messages(action_prompt, self.latched_conversation_text if uses_selected_text else ''):
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
        else:
            if r.exception is not None:
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
        else:
            if self.latched_conversation_text:
                st = self.latched_conversation_text
                if len(st) > 200:
                    st = st[:200] + '…'
                msg = f"<h3>{_('Selected text')}</h3><i>{st}</i>"
                msg += self.quick_actions_as_html
                msg += '<p>' + _('Or, type a question to the AI below, for example:') + '<br>'
                msg += '<i>Summarize this book.</i>'
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
                cost = f'{self.session_cost:.2f}'.rstrip('0').rstrip('.') + f' {self.session_cost_currency}'
            self.api_usage_label.setText(f'{_("Queries:")} {self.current_api_call_number} @ {_("Cost")}: {cost}')
        else:
            self.api_usage_label.setText(f'{_("Queries:")} {self.current_api_call_number}')

    def save_as_note(self):
        if self.conversation_history.response_count > 0 and self.latched_conversation_text:
            if not self.current_selected_text:
                return error_dialog(self, _('No selected text'), _('Cannot save note as there is currently no selected text'), show=True)
            self.add_note_requested.emit(
                format_llm_note(self.conversation_history, self.assistant_name), vprefs.get('llm_highlight_style', ''))

    def get_conversation_history_for_specific_response(self, message_index: int) -> ConversationHistory | None:
        if not (0 <= message_index < len(self.conversation_history)):
            return None
        ans = self.conversation_history.at(message_index)
        if not ans.from_assistant:
            return None
        return self.conversation_history.only(message_index)

    def save_specific_note(self, message_index: int) -> None:
        if not self.current_selected_text:
            return error_dialog(self, _('No selected text'), _('Cannot save note as there is currently no selected text'), show=True)
        history_for_record = self.get_conversation_history_for_specific_response(message_index)
        self.add_note_requested.emit(
            format_llm_note(history_for_record, self.assistant_name), vprefs.get('llm_highlight_style', ''))

    def show_reasoning(self, message_index: int) -> None:
        h = self.get_conversation_history_for_specific_response(message_index)
        m = h.at(len(h)-1)
        if m.reasoning:
            d = QDialog(self)
            l = QVBoxLayout(d)
            b = QTextBrowser(d)
            b.setPlainText(m.reasoning)
            l.addWidget(b)
            d.setWindowTitle(_('Reasoning used by AI'))
            d.setWindowIcon(QIcon.ic(reasoning_icon))
            bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, d)
            l.addWidget(bb)
            d.resize(600, 500)
            d.exec()

    def copy_specific_note(self, message_index: int) -> None:
        history_for_record = self.get_conversation_history_for_specific_response(message_index)
        text = format_llm_note(history_for_record, self.assistant_name)
        if text:
            QApplication.instance().clipboard().setText(text)

    def copy_to_clipboard(self) -> None:
        text = format_llm_note(self.conversation_history, self.assistant_name)
        if text:
            QApplication.instance().clipboard().setText(text)

    def on_chat_link_clicked(self, qurl: QUrl):
        match qurl.host():
            case self.save_note_hostname:
                index = int(qurl.path().strip('/'))
                self.save_specific_note(index)
            case self.copy_hostname:
                index = int(qurl.path().strip('/'))
                self.copy_specific_note(index)
            case self.reasoning_hostname:
                index = int(qurl.path().strip('/'))
                self.show_reasoning(index)
            case self.configure_ai_hostname:
                self.show_settings()
            case self.quick_action_hostname:
                name = from_hex_unicode(qurl.path().strip('/'))
                for ac in current_actions():
                    if ac.name == name:
                        self.activate_action(ac)
                        break

    def set_all_inputs_enabled(self, enabled):
        for i in range(self.quick_actions_layout.count()):
            widget = self.quick_actions_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(enabled)
        self.result_display.set_input_enabled(enabled)


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
        self.help_label = la = QLabel('<p>' + _(
            'The prompt is a template. If you want the prompt to operate on the currently selected'
            ' text, add <b>{0}</b> to the end of the prompt. Similarly, use <b>{1}</b>'
            ' when you want the AI to respond in the current language (not all AIs work well with all languages).'
        ).format('selected', 'Respond in {language}'))
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

    def get_action(self) -> Action:
        title = self.name_edit.text().strip()
        return Action(f'custom-{title}', title, self.prompt_edit.toPlainText().strip())

    def accept(self) -> None:
        ac = self.get_action()
        if not ac.human_name:
            return error_dialog(self, _('No name specified'), _('You must specify a name for the Quick action'), show=True)
        if not ac.prompt_template:
            return error_dialog(self, _('No prompt specified'), _('You must specify a prompt for the Quick action'), show=True)
        try:
            ac.prompt_text()
        except Exception as e:
            return error_dialog(self, _('Invalid prompt'), _('The prompt you specified is not valid. Error: {}').format(e), show=True)
        super().accept()


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
        item.setToolTip(textwrap.fill(ac.prompt_template))

    def load_actions_from_prefs(self):
        self.actions_list.clear()
        for ac in sorted(current_actions(include_disabled=True), key=lambda ac: primary_sort_key(ac.human_name)):
            self.action_as_item(ac)

    def add_action(self):
        dialog = ActionEditDialog(parent=self)
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
        dialog = ActionEditDialog(action, parent=self)
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


def develop(show_initial_messages: bool = False):
    app = Application([])
    # return LLMSettingsDialog().exec()
    d = QDialog()
    l = QVBoxLayout(d)
    l.setContentsMargins(0, 0, 0, 0)
    llm = LLMPanel(d)
    llm.update_with_text('developing my thoughts on the AI apocalypse')
    h = llm.conversation_history
    if show_initial_messages:
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
        h.response_count = 2
        llm.show_ai_conversation()
        llm.update_ui_state()
    l.addWidget(llm)
    d.exec()
    del app


if __name__ == '__main__':
    develop()
