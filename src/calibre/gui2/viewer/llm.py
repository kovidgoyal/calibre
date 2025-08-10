# License: GPL v3 Copyright: 2025, Amir Tehrani and Kovid Goyal

import json
from threading import Thread
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs

from qt.core import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QEvent, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QIcon, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, Qt, QTextBrowser,
    QTextEdit, QVBoxLayout, QWidget, pyqtSignal
)

from calibre.gui2.viewer.config import vprefs
from calibre.utils.localization import _
from polyglot.binary import as_hex_unicode, from_hex_unicode

# --- Backend Abstraction & Cost Data ---
MODEL_COSTS = {
    # Anthropic
    'anthropic/claude-3-haiku': (0.25, 1.25),
    'anthropic/claude-3.5-sonnet': (3.00, 15.00),
    'anthropic/claude-3.7-sonnet': (3.00, 15.00),
    'anthropic/claude-sonnet-4': (3.00, 15.00),

    # DeepSeek
    'deepseek/deepseek-chat-v3-0324': (0.18, 0.72),

    # Google
    'google/gemini-1.5-flash': (0.075, 0.30),
    'google/gemini-1.5-pro': (1.25, 5.00),
    'google/gemini-2.0-flash-001': (0.10, 0.40),
    'google/gemini-2.5-flash': (0.30, 2.50),
    'google/gemini-2.5-flash-lite': (0.10, 0.40),
    'google/gemini-2.5-pro': (1.25, 10.00),

    # Meta
    'meta-llama/llama-3.1-8b-instruct': (0.015, 0.02),
    'meta-llama/llama-3.1-70b-instruct': (0.10, 0.28),

    # Mistral
    'mistralai/mistral-7b-instruct': (0.028, 0.054),
    'mistralai/mistral-nemo': (0.008, 0.05),

    # MoonshotAI
    'moonshotai/kimi-k2': (0.14, 2.49),

    # OpenAI
    'openai/gpt-4.1-mini': (0.40, 1.60),
    'openai/gpt-4o': (2.50, 10.00),
    'openai/gpt-4o-mini': (0.15, 0.60),
    'openai/gpt-5': (1.25, 10.00),
    'openai/gpt-5-mini': (0.25, 2.00),
    'openai/gpt-oss-120b': (0.072, 0.28),

    # Qwen
    'qwen/qwen3-coder': (0.20, 0.80),

    # ZhipuAI
    'z-ai/glm-4.5': (0.20, 0.80),

    # Default Fallback
    'default': (0.50, 1.50)
}

API_PROVIDERS = {
    'openrouter': {
        'url': "https://openrouter.ai/api/v1/chat/completions",
        'headers': lambda api_key: {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/kovidgoyal/calibre',
            'X-Title': 'Calibre E-book Viewer'
        },
        'payload': lambda model_id, messages: {
            "model": model_id,
            "messages": messages
        },
        'parse_response': lambda r_json: (
            r_json['choices'][0]['message']['content'],
            r_json.get('usage', {'prompt_tokens': 0, 'completion_tokens': 0})
        )
    }
}
# --- End Backend Abstraction ---


class LLMAPICall(Thread):
    def __init__(self, conversation_history, api_key, model_id, signal_emitter, provider_config):
        super().__init__()
        self.conversation_history = conversation_history
        self.api_key = api_key
        self.model_id = model_id
        self.signal_emitter = signal_emitter
        self.provider_config = provider_config
        self.daemon = True

    def run(self):
        try:
            url = self.provider_config['url']
            headers = self.provider_config['headers'](self.api_key)
            payload = self.provider_config['payload'](self.model_id, self.conversation_history)

            encoded_data = json.dumps(payload).encode('utf-8')
            req = request.Request(url, data=encoded_data, headers=headers, method='POST')

            with request.urlopen(req, timeout=90) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)

            if 'error' in response_json:
                raise Exception(response_json['error'].get('message', 'Unknown API error'))
            if not response_json.get('choices'):
                raise Exception("API response did not contain any choices.")

            result_text, usage_data = self.provider_config['parse_response'](response_json)
            self.signal_emitter.emit(result_text, usage_data)

        except HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_body)
                msg = error_json.get('error', {}).get('message', error_body)
            except json.JSONDecodeError:
                msg = error_body
            self.signal_emitter.emit(f"<p style='color:red;'><b>API Error ({e.code}):</b> {msg}</p>", {})
        except URLError as e:
            self.signal_emitter.emit(f"<p style='color:red;'><b>Network Error:</b> {e.reason}</p>", {})
        except Exception as e:
            self.signal_emitter.emit(f"<p style='color:red;'><b>An unexpected error occurred:</b> {e}</p>", {})


class LLMPanel(QWidget):
    response_received = pyqtSignal(str, dict)
    add_note_requested = pyqtSignal(dict)
    _SAVE_ACTION_URL_SCHEME = 'calibre-llm-action'
    DEFAULT_ACTIONS = [
        {'name': 'Summarize', 'prompt': 'Provide a concise summary of the following text.'},
        {'name': 'Explain Simply', 'prompt': 'Explain the following text in simple, easy-to-understand terms.'},
        {'name': 'Key Points', 'prompt': 'Extract the key points from the following text as a bulleted list.'},
        {'name': 'Define Terms', 'prompt': 'Identify and define any technical or complex terms in the following text.'},
        {'name': 'Correct Grammar', 'prompt': 'Correct any grammatical errors in the following text and provide the corrected version.'},
        {'name': 'Translate to English', 'prompt': 'Translate the following text into English.'},
    ]

    def __init__(self, parent=None, viewer=None, lookup_widget=None):
        super().__init__(parent)
        self.viewer = viewer
        self.lookup_widget = lookup_widget

        self.conversation_history = []
        self.last_response_text = ''
        self.latched_highlight_uuid = None
        self.latched_conversation_text = None
        self.session_api_calls = 0
        self.session_cost = 0.0
        self.book_title = ''
        self.book_authors = ''

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.quick_actions_group = QGroupBox(self)
        self.quick_actions_group.setTitle('Quick Actions')
        self.quick_actions_layout = QGridLayout(self.quick_actions_group)
        self.layout.addWidget(self.quick_actions_group)
        self.rebuild_actions_ui()

        custom_prompt_group = QGroupBox(self)
        custom_prompt_group.setTitle('Custom Prompt')
        custom_prompt_layout = QHBoxLayout(custom_prompt_group)
        self.custom_prompt_edit = QLineEdit(self)
        self.custom_prompt_edit.setPlaceholderText('Or, enter your own request...')
        self.custom_prompt_button = QPushButton('Send', self)
        custom_prompt_layout.addWidget(self.custom_prompt_edit)
        custom_prompt_layout.addWidget(self.custom_prompt_button)
        self.layout.addWidget(custom_prompt_group)

        self.result_display = QTextBrowser(self)
        self.result_display.setOpenExternalLinks(False)
        self.result_display.setMinimumHeight(150)
        self.result_display.anchorClicked.connect(self._on_chat_link_clicked)
        self.layout.addWidget(self.result_display)

        response_actions_layout = QHBoxLayout()
        self.save_note_button = QPushButton(QIcon.ic('plus.png'), 'Save as Note', self)
        self.save_note_button.clicked.connect(self.save_as_note)

        self.new_chat_button = QPushButton(QIcon.ic('edit-clear.png'), 'New Chat', self)
        self.new_chat_button.setToolTip('Clear the current conversation history and start a new one')
        self.new_chat_button.clicked.connect(self.start_new_conversation)
        self.new_chat_button.setEnabled(False)

        response_actions_layout.addWidget(self.save_note_button)
        response_actions_layout.addWidget(self.new_chat_button)
        response_actions_layout.addStretch()
        self.layout.addLayout(response_actions_layout)

        footer_layout = QHBoxLayout()
        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.api_usage_label = QLabel('API calls: 0 | Cost: ~$0.0000')
        footer_layout.addWidget(self.settings_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.api_usage_label)
        self.layout.addLayout(footer_layout)

        self.custom_prompt_button.clicked.connect(self.run_custom_prompt)
        self.custom_prompt_edit.returnPressed.connect(self.run_custom_prompt)
        self.response_received.connect(self.show_response)
        self.settings_button.clicked.connect(self.show_settings)
        self.show_initial_message()

    def update_book_metadata(self, metadata):
        self.book_title = metadata.get('title', '')
        authors = metadata.get('authors', [])
        self.book_authors = ' & '.join(authors)

    def rebuild_actions_ui(self):
        while self.quick_actions_layout.count():
            child = self.quick_actions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        actions_json = vprefs.get('llm_quick_actions', json.dumps(self.DEFAULT_ACTIONS))
        try:
            actions = json.loads(actions_json)
        except json.JSONDecodeError:
            actions = self.DEFAULT_ACTIONS
        positions = [(i, j) for i in range(4) for j in range(2)]
        for i, action in enumerate(actions):
            if i >= len(positions):
                break
            button = QPushButton(action['name'], self)
            button.clicked.connect(lambda _, p=action['prompt']: self.start_api_call(p))
            row, col = positions[i]
            self.quick_actions_layout.addWidget(button, row, col)

    def show_settings(self):
        dialog = LLMSettingsDialog(self)
        dialog.actions_updated.connect(self.rebuild_actions_ui)
        dialog.exec()

    def show_initial_message(self):
        self.save_note_button.setEnabled(False)
        api_key_hex = vprefs.get('llm_api_key', '') or ''
        api_key = from_hex_unicode(api_key_hex)
        if not api_key:
            self.show_response("<p style='color:orange;'><b>Welcome!</b> Please add your OpenRouter.ai API key by clicking the <b>⚙️ Settings</b> button below.</p>", {})
        else:
            self.show_response("<b>Ready.</b> Select text in the book to begin.", {})

    def update_with_text(self, text, highlight_data, is_read_only_view=False):
        new_uuid = highlight_data.get('uuid') if highlight_data else None

        if not text and not new_uuid:
            if self.latched_conversation_text is not None or self.latched_highlight_uuid is not None:
                self.start_new_conversation()
            return

        if is_read_only_view:
            self.latched_highlight_uuid = new_uuid
            self.latched_conversation_text = text
            return

        start_new_convo = False
        if new_uuid != self.latched_highlight_uuid:
            start_new_convo = True
        elif new_uuid is None and text != self.latched_conversation_text:
            start_new_convo = True

        if start_new_convo:
            self.conversation_history = []
            self.last_response_text = ''
            self.latched_highlight_uuid = new_uuid
            self.latched_conversation_text = text

            if text:
                self.show_response(f"<b>Selected:</b><br><i>'{text[:200]}...'</i>", {})
            else:
                self.show_response("<b>Ready.</b> Ask a follow-up question.", {})

        if self.latched_highlight_uuid:
            self.save_note_button.setToolTip('Append this response to the existing highlight\'s note')
        else:
            self.save_note_button.setToolTip('Create a new highlight for the selected text and save this response as its note')

    def run_custom_prompt(self):
        prompt = self.custom_prompt_edit.text().strip()
        if prompt:
            self.start_api_call(prompt)

    def start_new_conversation(self):
        self.conversation_history = []
        self.last_response_text = ''
        self.latched_highlight_uuid = None
        self.latched_conversation_text = None

        self.new_chat_button.setEnabled(False)
        self.save_note_button.setEnabled(False)
        self.show_initial_message()

    def _render_conversation_html(self, thinking=False):
        base_table_style = "width: 95%; border-spacing: 0px; margin: 8px 5px;"
        base_cell_style = "padding: 8px; vertical-align: top;"
        text_style = "color: #E2E8F0;"
        user_bgcolor = "#2D3748"
        assistant_bgcolor = "#4A5568"
        thinking_style = "color: #A0AEC0; font-style: italic; margin: 5px; padding: 8px;"
        save_button_style = (
            "color: #E2E8F0; text-decoration: none; font-weight: bold; "
            "font-family: monospace; padding: 2px 6px; border: 1px solid #A0AEC0; border-radius: 4px;"
        )
        html_output = ''
        for i, message in enumerate(self.conversation_history):
            role = message.get('role')
            content_for_display = message.get('content', '').replace('\n', '<br>')
            if role == 'user':
                bgcolor = user_bgcolor
                label = "You"
                html_output += f'''
                <table style="{base_table_style}" bgcolor="{bgcolor}" cellspacing="0" cellpadding="0">
                    <tr><td style="{base_cell_style}"><p style="{text_style}"><b>{label}:</b><br>{content_for_display}</p></td></tr>
                </table>'''
            elif role == 'assistant':
                bgcolor = assistant_bgcolor
                label = "Assistant"
                save_button_href = f'http://{self._SAVE_ACTION_URL_SCHEME}/save?index={i}'
                html_output += f'''
                <table style="{base_table_style}" bgcolor="{bgcolor}" cellspacing="0" cellpadding="0">
                    <tr>
                        <td style="{base_cell_style}"><p style="{text_style}"><b>{label}:</b><br>{content_for_display}</p></td>
                        <td style="padding: 8px; width: 60px; text-align: center; vertical-align: middle;">
                            <a style="{save_button_style}" href="{save_button_href}" title="Save this specific response to the note">[ Save ]</a>
                        </td>
                    </tr>
                </table>'''
        if thinking:
            html_output += f'<div style="{thinking_style}"><i>Querying model...</i></div>'
        return html_output

    def start_api_call(self, action_prompt):
        api_key_hex = vprefs.get('llm_api_key', '') or ''
        api_key = from_hex_unicode(api_key_hex)
        if not api_key:
            self.show_response("<p style='color:orange;'><b>API Key Missing.</b> Click the <b>⚙️ Settings</b> button to add your key.</p>", {})
            return
        if not self.latched_conversation_text:
            self.show_response("<p style='color:red;'><b>Error:</b> No text is selected for this conversation.</p>", {})
            return

        is_first_message = not self.conversation_history
        if is_first_message:
            display_prompt_content = f"{action_prompt}\n\n<i>On text: \"{self.latched_conversation_text[:100]}...\"</i>"
        else:
            display_prompt_content = action_prompt
        self.conversation_history.append({'role': 'user', 'content': display_prompt_content})

        context_header = ""
        if self.book_title:
            context_header += f"The user is currently reading the book \"{self.book_title}\""
            if self.book_authors:
                context_header += f" by {self.book_authors}."
            else:
                context_header += "."

        api_prompt_content = (
            f"{context_header}\n\n"
            f"{action_prompt}\n\n"
            f"---\n\n"
            f"Text to analyze:\n\n"
            f"\"{self.latched_conversation_text}\""
        )

        api_call_history = list(self.conversation_history)
        api_call_history[-1] = {'role': 'user', 'content': api_prompt_content}

        self.result_display.setHtml(self._render_conversation_html(thinking=True))
        self.result_display.verticalScrollBar().setValue(self.result_display.verticalScrollBar().maximum())
        self.set_all_inputs_enabled(False)

        model_id = vprefs.get('llm_model_id', 'google/gemini-1.5-flash')
        provider_config = API_PROVIDERS['openrouter']
        api_call_thread = LLMAPICall(
            api_call_history, api_key, model_id, self.response_received, provider_config
        )
        api_call_thread.start()

    def show_response(self, response_text, usage_data):
        self.last_response_text = ''
        is_error_or_status = "<b>" in response_text

        if not is_error_or_status:
            self.session_api_calls += 1
            self.update_cost(usage_data)
            self.last_response_text = response_text
            self.conversation_history.append({'role': 'assistant', 'content': response_text})
            self.new_chat_button.setEnabled(True)

        self.save_note_button.setEnabled(bool(self.last_response_text) and bool(self.latched_conversation_text))

        if is_error_or_status:
            self.result_display.setHtml(response_text)
        else:
            self.result_display.setHtml(self._render_conversation_html())

        self.result_display.verticalScrollBar().setValue(self.result_display.verticalScrollBar().maximum())
        self.set_all_inputs_enabled(True)
        self.custom_prompt_edit.clear()

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
        self.api_usage_label.setText(f'API calls: {self.session_api_calls} | Cost: ~${self.session_cost:.4f}')

    def save_as_note(self):
        if self.last_response_text and self.latched_conversation_text:
            payload = {
                'highlight': self.latched_highlight_uuid,
                'conversation_history': self.conversation_history
            }
            self.add_note_requested.emit(payload)

    def save_specific_note(self, message_index):
        if not (0 <= message_index < len(self.conversation_history)):
            return
        target_message = self.conversation_history[message_index]
        if target_message.get('role') != 'assistant':
            return
        history_for_record = self.conversation_history[:message_index + 1]
        payload = {
            'highlight': self.latched_highlight_uuid,
            'conversation_history': history_for_record
        }
        self.add_note_requested.emit(payload)

    def _on_chat_link_clicked(self, qurl):
        url_str = qurl.toString()
        parsed_url = urlparse(url_str)
        if parsed_url.hostname == self._SAVE_ACTION_URL_SCHEME and parsed_url.path == '/save':
            query_params = parse_qs(parsed_url.query)
            index_str = query_params.get('index', [None])[0]
            if index_str is not None:
                try:
                    index = int(index_str)
                    self.save_specific_note(index)
                except (ValueError, TypeError):
                    pass
            return

    def set_all_inputs_enabled(self, enabled):
        for i in range(self.quick_actions_layout.count()):
            widget = self.quick_actions_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(enabled)
        self.custom_prompt_edit.setEnabled(enabled)
        self.custom_prompt_button.setEnabled(enabled)

class ActionEditDialog(QDialog):
    def __init__(self, action=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Quick Action' if action else 'Add Quick Action')
        self.layout = QFormLayout(self)
        self.name_edit = QLineEdit(self)
        self.prompt_edit = QTextEdit(self)
        self.prompt_edit.setAcceptRichText(False)
        self.prompt_edit.setMinimumHeight(100)
        self.layout.addRow('Button Name:', self.name_edit)
        self.layout.addRow('System Prompt:', self.prompt_edit)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        if action:
            self.name_edit.setText(action.get('name', ''))
            self.prompt_edit.setPlainText(action.get('prompt', ''))
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

    def get_action(self):
        return {'name': self.name_edit.text().strip(), 'prompt': self.prompt_edit.toPlainText().strip()}

class LLMSettingsDialog(QDialog):
    actions_updated = pyqtSignal()
    DEFAULT_ACTIONS = LLMPanel.DEFAULT_ACTIONS
    COLOR_MAP = {
        'yellow': 'Yellow highlight',
        'green': 'Green highlight',
        'blue': 'Blue highlight',
        'red': 'Pink highlight',
        'purple': 'Purple highlight',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LLM Settings (OpenRouter)')
        self.setMinimumWidth(550)
        self.layout = QVBoxLayout(self)
        api_model_layout = QFormLayout()
        api_key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit(self)
        self.api_key_edit.setPlaceholderText('Paste your OpenRouter.ai API key here')
        self.clear_api_key_button = QPushButton('Clear', self)
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.clear_api_key_button)
        self.model_edit = QLineEdit(self)
        self.model_edit.setPlaceholderText('google/gemini-flash-1.5')

        self.highlight_color_combo = QComboBox(self)

        model_label = QLabel('Model (<a href="https://openrouter.ai/models">see list</a>):')
        model_label.setOpenExternalLinks(True)
        api_model_layout.addRow('API Key:', api_key_layout)
        api_model_layout.addRow(model_label, self.model_edit)
        api_model_layout.addRow('Highlight Color:', self.highlight_color_combo)
        self.layout.addLayout(api_model_layout)
        self.layout.addWidget(QLabel('<h3>Quick Actions</h3>'))
        self.actions_list = QListWidget(self)
        self.actions_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layout.addWidget(self.actions_list)
        actions_button_layout = QHBoxLayout()
        self.add_button = QPushButton('Add...')
        self.edit_button = QPushButton('Edit...')
        self.remove_button = QPushButton('Remove')
        self.reset_button = QPushButton('Reset to Defaults')
        actions_button_layout.addWidget(self.add_button)
        actions_button_layout.addWidget(self.edit_button)
        actions_button_layout.addWidget(self.remove_button)
        actions_button_layout.addStretch()
        actions_button_layout.addWidget(self.reset_button)
        self.layout.addLayout(actions_button_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.clear_api_key_button.clicked.connect(self.clear_api_key)
        self.add_button.clicked.connect(self.add_action)
        self.edit_button.clicked.connect(self.edit_action)
        self.remove_button.clicked.connect(self.remove_action)
        self.reset_button.clicked.connect(self.reset_actions)
        self.actions_list.itemDoubleClicked.connect(self.edit_action)
        self.load_settings()
        self.actions_list.setFocus()

    def load_settings(self):
        self.api_key_edit.setText(from_hex_unicode(vprefs.get('llm_api_key', '')))
        self.model_edit.setText(vprefs.get('llm_model_id', 'google/gemini-flash-1.5'))

        self.highlight_color_combo.clear()
        current_color_internal_name = vprefs.get('llm_highlight_color', 'yellow')

        for internal_name, friendly_name in self.COLOR_MAP.items():
            self.highlight_color_combo.addItem(friendly_name, internal_name)

        index_to_set = self.highlight_color_combo.findData(current_color_internal_name)
        if index_to_set != -1:
            self.highlight_color_combo.setCurrentIndex(index_to_set)

        self.load_actions_from_prefs()

    def load_actions_from_prefs(self):
        self.actions_list.clear()
        actions_json = vprefs.get('llm_quick_actions', json.dumps(self.DEFAULT_ACTIONS))
        try:
            actions = json.loads(actions_json)
        except json.JSONDecodeError:
            actions = self.DEFAULT_ACTIONS
        for action in actions:
            item = QListWidgetItem(action['name'], self.actions_list)
            item.setData(Qt.ItemDataRole.UserRole, action)

    def add_action(self):
        dialog = ActionEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action = dialog.get_action()
            if action['name'] and action['prompt']:
                item = QListWidgetItem(action['name'], self.actions_list)
                item.setData(Qt.ItemDataRole.UserRole, action)

    def edit_action(self):
        item = self.actions_list.currentItem()
        if not item:
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        dialog = ActionEditDialog(action, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.get_action()
            if new_action['name'] and new_action['prompt']:
                item.setText(new_action['name'])
                item.setData(Qt.ItemDataRole.UserRole, new_action)

    def remove_action(self):
        item = self.actions_list.currentItem()
        if item and QMessageBox.question(self, 'Confirm Remove', f"Remove the '{item.text()}' action?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.actions_list.takeItem(self.actions_list.row(item))

    def reset_actions(self):
        if QMessageBox.question(self, 'Confirm Reset', "Reset all quick actions to their default state?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            vprefs.set('llm_quick_actions', json.dumps(self.DEFAULT_ACTIONS))
            self.load_actions_from_prefs()

    def clear_api_key(self):
        self.api_key_edit.clear()

    def accept(self):
        vprefs.set('llm_api_key', as_hex_unicode(self.api_key_edit.text().strip()))
        vprefs.set('llm_model_id', self.model_edit.text().strip() or 'google/gemini-flash-1.5')

        selected_internal_name = self.highlight_color_combo.currentData()
        vprefs.set('llm_highlight_color', selected_internal_name or 'yellow')

        actions = []
        for i in range(self.actions_list.count()):
            item = self.actions_list.item(i)
            actions.append(item.data(Qt.ItemDataRole.UserRole))
        vprefs.set('llm_quick_actions', json.dumps(actions))
        self.actions_updated.emit()
        super().accept()