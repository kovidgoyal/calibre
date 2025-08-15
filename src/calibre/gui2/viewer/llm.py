# License: GPL v3 Copyright: 2025, Amir Tehrani and Kovid Goyal

import json
from threading import Thread
from urllib import request

from qt.core import (
    QAbstractItemView, QDialog, QDialogButtonBox, QEvent, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, Qt, QTextBrowser,
    QTextEdit, QVBoxLayout, QWidget, pyqtSignal
)

from calibre.gui2.viewer.config import vprefs
from calibre.utils.localization import _
from polyglot.binary import as_hex_unicode, from_hex_unicode


class LLMAPICall(Thread):
    def __init__(self, selected_text, prompt_action, api_key, model_id, signal_emitter):
        super().__init__()
        self.selected_text = selected_text
        self.prompt_action = prompt_action
        self.api_key = api_key
        self.model_id = model_id
        self.signal_emitter = signal_emitter
        self.daemon = True

    def run(self):
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/kovidgoyal/calibre', 'X-Title': 'Calibre E-book Viewer'
            }
            full_prompt = f"{self.prompt_action}\n\n---\n\nText to analyze:\n\n\"{self.selected_text}\""
            payload = {"model": self.model_id, "messages": [{"role": "user", "content": full_prompt}]}
            encoded_data = json.dumps(payload).encode('utf-8')
            req = request.Request(url, data=encoded_data, headers=headers, method='POST')
            with request.urlopen(req, timeout=90) as response:
                response_data = response.read().decode('utf-8')
                response_json = json.loads(response_data)
                if response.status != 200:
                    error_msg = response_json.get('error', {}).get('message', f"HTTP Error {response.status}: {response.reason}")
                    raise Exception(error_msg)
            if 'error' in response_json:
                raise Exception(response_json['error'].get('message', 'Unknown API error'))
            if not response_json.get('choices'):
                raise Exception("API response did not contain any choices.")
            result_text = response_json['choices'][0]['message']['content']
            self.signal_emitter.emit(result_text)
        except Exception as e:
            self.signal_emitter.emit(f"<p style='color:red;'><b>An error occurred:</b> {e}</p>")


class LLMPanel(QWidget):
    response_received = pyqtSignal(str)
    DEFAULT_ACTIONS = [
        {'name': 'Summarize', 'prompt': 'Provide a concise summary of the following text.'},
        {'name': 'Explain Simply', 'prompt': 'Explain the following text in simple, easy-to-understand terms.'},
        {'name': 'Key Points', 'prompt': 'Extract the key points from the following text as a bulleted list.'},
        {'name': 'Define Terms', 'prompt': 'Identify and define any technical or complex terms in the following text.'},
        {'name': 'Correct Grammar', 'prompt': 'Correct any grammatical errors in the following text and provide the corrected version.'},
        {'name': 'Translate to English', 'prompt': 'Translate the following text into English.'},
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_text = ''
        self.session_api_calls = 0
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.quick_actions_group = QGroupBox('Quick Actions')
        self.quick_actions_layout = QGridLayout(self.quick_actions_group)
        self.layout.addWidget(self.quick_actions_group)
        self.rebuild_actions_ui()
        custom_prompt_group = QGroupBox('Custom Prompt')
        custom_prompt_layout = QHBoxLayout(custom_prompt_group)
        self.custom_prompt_edit = QLineEdit(self)
        self.custom_prompt_edit.setPlaceholderText('Or, enter your own request...')
        self.custom_prompt_button = QPushButton('Send', self)
        custom_prompt_layout.addWidget(self.custom_prompt_edit)
        custom_prompt_layout.addWidget(self.custom_prompt_button)
        self.layout.addWidget(custom_prompt_group)
        self.result_display = QTextBrowser(self)
        self.result_display.setOpenExternalLinks(True)
        self.result_display.setMinimumHeight(150)
        self.layout.addWidget(self.result_display)
        footer_layout = QHBoxLayout()
        self.settings_button = QPushButton("⚙️ Settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.api_usage_label = QLabel('API calls: 0')
        footer_layout.addWidget(self.settings_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.api_usage_label)
        self.layout.addLayout(footer_layout)
        self.custom_prompt_button.clicked.connect(self.run_custom_prompt)
        self.custom_prompt_edit.returnPressed.connect(self.run_custom_prompt)
        self.response_received.connect(self.show_response)
        self.settings_button.clicked.connect(self.show_settings)
        self.show_initial_message()

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
        api_key_hex = vprefs.get('llm_api_key', '') or ''
        api_key = from_hex_unicode(api_key_hex)
        if not api_key:
            self.show_response("<p style='color:orange;'><b>Welcome!</b> Please add your OpenRouter.ai API key by clicking the <b>⚙️ Settings</b> button below.</p>")
        else:
            self.show_response("<b>Ready.</b> Select text in the book to begin.")

    def update_with_text(self, text):
        self.selected_text = text
        api_key_hex = vprefs.get('llm_api_key', '') or ''
        if not from_hex_unicode(api_key_hex):
            self.show_initial_message()
            return
        if text:
            self.show_response(f"<b>Selected:</b><br><i>'{self.selected_text[:200]}...'</i>")
        else:
            self.show_response("<b>Ready.</b> Select text in the book to begin.")

    def run_custom_prompt(self):
        prompt = self.custom_prompt_edit.text().strip()
        if prompt:
            self.start_api_call(prompt)

    def start_api_call(self, action_prompt):
        api_key_hex = vprefs.get('llm_api_key', '') or ''
        api_key = from_hex_unicode(api_key_hex)
        if not api_key:
            self.show_response("<p style='color:orange;'><b>API Key Missing.</b> Click the <b>⚙️ Settings</b> button to add your key.</p>")
            return
        if not self.selected_text:
            self.show_response("<p style='color:red;'><b>Error:</b> No text is selected.</p>")
            return
        self.result_display.setHtml('<p style="color: #888;"><i>Querying model...</i></p>')
        self.set_all_inputs_enabled(False)
        model_id = vprefs.get('llm_model_id', 'google/gemini-flash-1.5')
        api_call_thread = LLMAPICall(self.selected_text, action_prompt, api_key, model_id, self.response_received)
        api_call_thread.start()

    def show_response(self, response_text):
        if "<b>" not in response_text:
            self.session_api_calls += 1
            self.api_usage_label.setText(f'API calls: {self.session_api_calls}')
        self.result_display.setHtml(response_text.replace('\n', '<br>'))
        self.set_all_inputs_enabled(True)
        self.custom_prompt_edit.clear()

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
        model_label = QLabel('Model (<a href="https://openrouter.ai/models">see list</a>):')
        model_label.setOpenExternalLinks(True)
        api_model_layout.addRow('API Key:', api_key_layout)
        api_model_layout.addRow(model_label, self.model_edit)
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
        actions = []
        for i in range(self.actions_list.count()):
            item = self.actions_list.item(i)
            actions.append(item.data(Qt.ItemDataRole.UserRole))
        vprefs.set('llm_quick_actions', json.dumps(actions))
        self.actions_updated.emit()
        super().accept()