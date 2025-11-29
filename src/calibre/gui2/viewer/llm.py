#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net> and Amir Tehrani

import string
import textwrap
from collections.abc import Iterator
from functools import lru_cache
from typing import Any, NamedTuple

from qt.core import (
    QAbstractItemView,
    QCheckBox,
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
    QPlainTextEdit,
    QPushButton,
    QSize,
    Qt,
    QTabWidget,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai import ChatMessage, ChatMessageType
from calibre.ai.config import ConfigureAI
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import Application, error_dialog
from calibre.gui2.chat_widget import Button
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.llm import ConverseWidget, prompt_sep
from calibre.gui2.viewer.config import vprefs
from calibre.gui2.viewer.highlights import HighlightColorCombo
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import ui_language_as_english
from polyglot.binary import from_hex_unicode


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
        return pt.format(selected=selected_text, language=ui_language_as_english()).strip()


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
        x = Action(f'custom-{title}', title, c['prompt_template'], is_builtin=False, is_disabled=c['disabled'])
        if include_disabled or not x.is_disabled:
            yield x


def get_language_instruction() -> str:
    if vprefs['llm_localized_results'] != 'always':
        return ''
    lang = ui_language_as_english()
    return f'If you can speak in {lang}, then respond in {lang}.'


class LLMPanel(ConverseWidget):
    add_note_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.save_note_hostname = f'{self.hid}.save.calibre'

        self.latched_conversation_text = ''
        self.current_selected_text = ''
        self.book_title = ''
        self.book_authors = ''

    def add_buttons(self):
        self.add_button('save.png', _('&Save as note'), _('Save this conversation as a note on the current highlight')).clicked.connect(self.save_as_note)
        super().add_buttons()

    def update_book_metadata(self, metadata):
        self.book_title = metadata.get('title', '')
        authors = metadata.get('authors', [])
        self.book_authors = authors_to_string(authors)

    def activate_action(self, action: Action) -> None:
        self.start_api_call(action.prompt_text(self.latched_conversation_text), action.uses_selected_text)

    def settings_dialog(self) -> QDialog:
        return LLMSettingsDialog(self)

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

    def per_response_buttons(self, msgnum, msg):
        yield Button('save.png', f'http://{self.save_note_hostname}/{msgnum}', _(
            'Save this specific response as the note'))

    def create_initial_messages(self, action_prompt: str, selected_text: str) -> Iterator[ChatMessage]:
        if self.book_title:
            context_header = f'I am currently reading the book: {self.book_title}'
            if self.book_authors:
                context_header += f' by {self.book_authors}'
            if selected_text:
                context_header += '. I have some questions about content from this book.'
            else:
                context_header += '. I have some questions about this book.'
            context_header += ' When you answer the questions use markdown formatting for the answers wherever possible.'
            if language_instruction := get_language_instruction():
                context_header += ' ' + language_instruction
            yield ChatMessage(context_header, type=ChatMessageType.system)
        yield ChatMessage(action_prompt)

    def choose_action_message(self) -> str:
        msg = ''
        if self.latched_conversation_text:
            st = self.latched_conversation_text
            if len(st) > 200:
                st = st[:200] + '…'
            msg = f"<h3>{_('Selected text')}</h3><i>{st}</i>"
            msg += self.quick_actions_as_html(current_actions())
            msg += '<p>' + _('Or, type a question to the AI below, for example:') + '<br>'
            msg += '<i>Summarize this book.</i>'
        return msg

    def save_as_note(self):
        if self.conversation_history.response_count > 0 and self.latched_conversation_text:
            if not self.current_selected_text:
                return error_dialog(self, _('No selected text'), _('Cannot save note as there is currently no selected text'), show=True)
            self.add_note_requested.emit(
                self.conversation_history.format_llm_note(self.assistant_name),
                vprefs.get('llm_highlight_style', ''))

    def save_specific_note(self, message_index: int) -> None:
        if not self.current_selected_text:
            return error_dialog(self, _('No selected text'), _('Cannot save note as there is currently no selected text'), show=True)
        history_for_record = self.get_conversation_history_for_specific_response(message_index)
        self.add_note_requested.emit(
            history_for_record.format_llm_note(self.assistant_name), vprefs.get('llm_highlight_style', ''))

    def handle_chat_link(self, qurl: QUrl) -> bool:
        match qurl.host():
            case self.save_note_hostname:
                index = int(qurl.path().strip('/'))
                self.save_specific_note(index)
                return True
            case self.quick_action_hostname:
                name = from_hex_unicode(qurl.path().strip('/'))
                for ac in current_actions():
                    if ac.name == name:
                        self.activate_action(ac)
                        break
                return True
        return False


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
        return Action(f'custom-{title}', title, self.prompt_edit.toPlainText().strip(), is_builtin=False)

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
        self.localized_results = lr = QCheckBox(_('Ask the AI to respond in the current language'))
        lr.setToolTip('<p>' + _('Ask the AI to respond in the current calibre user interface language. Note that how well'
                        ' this works depends on the individual model being used. Different models support'
                        ' different languages.'))
        api_model_layout.addRow(lr)
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
        self.localized_results.setChecked(vprefs['llm_localized_results'] == 'always')
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
        vprefs.set('llm_localized_results', 'always' if self.localized_results.isChecked() else 'never')
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
