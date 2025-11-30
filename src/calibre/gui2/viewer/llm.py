#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net> and Amir Tehrani

import string
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from qt.core import QDialog, QUrl, QVBoxLayout, QWidget, pyqtSignal

from calibre.ai import ChatMessage, ChatMessageType
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import Application, error_dialog
from calibre.gui2.chat_widget import Button
from calibre.gui2.llm import ActionData, ConverseWidget, LLMActionsSettingsWidget, LLMSettingsDialogBase, LocalisedResults, prompt_sep
from calibre.gui2.viewer.config import vprefs
from calibre.gui2.viewer.highlights import HighlightColorCombo
from calibre.utils.localization import ui_language_as_english
from polyglot.binary import from_hex_unicode


class Action(ActionData):

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


def current_actions(include_disabled=False) -> Iterator[Action]:
    p = vprefs.get('llm_quick_actions') or {}
    return Action.unserialize(p, default_actions(), include_disabled)


class LLMSettingsDialog(LLMSettingsDialogBase):

    def __init__(self, parent=None):
        super().__init__(title=_('AI Settings'), name='llm-settings-dialog', prefs=vprefs, parent=parent)

    def custom_tabs(self) -> Iterator[str, str, QWidget]:
        yield 'config.png', _('Actions and &highlights'), LLMSettingsWidget(self)


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
        self.start_api_call(self.prompt_text_for_action(action), uses_selected_text=action.uses_selected_text)

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

    def get_language_instruction(self) -> str:
        if vprefs['llm_localized_results'] != 'always':
            return ''
        return self.language_instruction()

    def create_initial_messages(self, action_prompt: str, **kwargs: Any) -> Iterator[ChatMessage]:
        selected_text = self.latched_conversation_text if kwargs.get('uses_selected_text') else ''
        if self.book_title:
            context_header = f'I am currently reading the book: {self.book_title}'
            if self.book_authors:
                context_header += f' by {self.book_authors}'
            if selected_text:
                context_header += '. I have some questions about content from this book.'
            else:
                context_header += '. I have some questions about this book.'
            context_header += ' When you answer the questions use markdown formatting for the answers wherever possible.'
            if language_instruction := self.get_language_instruction():
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

    def prompt_text_for_action(self, action) -> str:
        return action.prompt_text(self.latched_conversation_text)

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

    def start_new_conversation(self) -> None:
        self.latched_conversation_text = ''
        super().start_new_conversation()

    def ready_to_start_api_call(self) -> str:
        if self.latched_conversation_text:
            return ''
        return _('No text is selected for this conversation.')


# Settings {{{

class HighlightWidget(HighlightColorCombo):

    def load_settings(self) -> None:
        if hsn := vprefs.get('llm_highlight_style'):
            self.highlight_style_name = hsn

    def commit(self) -> bool:
        selected_internal_name = self.currentData()
        vprefs.set('llm_highlight_style', selected_internal_name)
        return True


class LLMSettingsWidget(LLMActionsSettingsWidget):

    action_edit_help_text = '<p>' + _(
            'The prompt is a template. If you want the prompt to operate on the currently selected'
            ' text, add <b>{0}</b> to the end of the prompt. Similarly, use <b>{1}</b>'
            ' when you want the AI to respond in the current language (not all AIs work well with all languages).'
        ).format('{selected}', 'Respond in {language}')

    def get_actions_from_prefs(self) -> Iterator[ActionData]:
        yield from current_actions(include_disabled=True)

    def set_actions_in_prefs(self, s: dict[str, Any]) -> None:
        vprefs.set('llm_quick_actions', s)

    def create_custom_widgets(self) -> Iterator[str, QWidget]:
        yield _('&Highlight style:'), HighlightWidget(self)
        yield '', LocalisedResults(vprefs)
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
