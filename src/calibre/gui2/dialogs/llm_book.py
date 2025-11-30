#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Iterator
from functools import lru_cache
from typing import Any, NamedTuple

from qt.core import QDialog, QUrl, QVBoxLayout, QWidget

from calibre.ai import ChatMessage, ChatMessageType
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import Application, gprefs
from calibre.gui2.llm import ConverseWidget
from calibre.gui2.viewer.config import vprefs
from polyglot.binary import from_hex_unicode


def format_book_for_query(book: Metadata, is_first: bool, num_books: int) -> str:
    which = '' if num_books < 2 else ('first' if is_first else 'next')
    ans = f'The {which} book is: {book.title} by {book.format_authors()}.'
    left = get_allowed_fields() - {'title', 'authors'}
    if 'series' in left:
        ans += f' It is in the series: {book.series}.'
        left.discard('series'), left.discard('series_index')
    if 'tags' in left:
        ans += ' It is tagged with the following tags:' + book.format_tags() + '.'
        left.discard('tags')
    comments = []
    fields = []
    for field in left:
        m = book.metadata_for_field(field)
        if field == 'comments' or m['datatype'] == 'comments':
            comments.append(m.get('field'))
        else:
            fields.append(book.format_field(field))
    if fields:
        ans += ' It has the following additional metadata.'
        for name, val in fields:
            ans += f' {name}: {val}'
    if comments:
        ans += ' Some notes about this book: ' + comments
    return ans


def format_books_for_query(books: list[Metadata]) -> str:
    ans = 'I wish to discuss the following book. '
    if len(books) > 1:
        ans = 'I wish to discuss the following books. '
    for i, book in enumerate(books):
        ans += format_book_for_query(book, i == 0, len(books)) + '\n---------------\n\n'
    return ans


def get_allowed_fields() -> set[str]:
    return set()


class Action(NamedTuple):
    name: str
    human_name: str
    prompt_template: str
    is_builtin: bool = True
    is_disabled: bool = False

    @property
    def as_custom_action_dict(self) -> dict[str, Any]:
        return {'disabled': self.is_disabled, 'title': self.human_name, 'prompt_template': self.prompt_template}

    def prompt_text(self, books: list[Metadata]) -> str:
        pt = self.prompt_template
        return pt.format(
            books=format_books_for_query(books),
            books_word='book' if len(books) < 2 else 'books',
            plural_word='is' if len(books) < 2 else 'are',
        )


@lru_cache(2)
def default_actions() -> tuple[Action, ...]:
    return (
        Action('summarize', _('Summarize'), '{books} Provide a concise summary of the previously described {books_word}.'),
        Action('chapters', _('Chapters'), '{books} Provide a chapter by chapter summary of the previously described {books_word}.'),
        Action('read_next', _('Read next'), 'Suggest some good books to read after the previously described {books_word}.'),
        Action('universe', _('Universe'), 'Describe the fictional universe the previously described {books_word} {plural_word} set in.'
               ' Outline major plots, themes and characters in the universe.'),
        Action('series', _('Series'), 'Give the series the previously described {books_word} {plural_word} in.'
               ' List all the books in the series, in both published and internal chronological order.'
               ' Also describe any prominent spin-off series.')
    )


def current_actions(include_disabled=False):
    p = gprefs.get('llm_converse_quick_actions') or {}
    dd = p.get('disabled_default_actions', ())
    for x in default_actions():
        x = x._replace(is_disabled=x.name in dd)
        if include_disabled or not x.is_disabled:
            yield x
    for title, c in p.get('custom_actions', {}).items():
        x = Action(f'custom-{title}', title, c['prompt_template'], is_builtin=False, is_disabled=c['disabled'])
        if include_disabled or not x.is_disabled:
            yield x


class LLMPanel(ConverseWidget):
    NOTE_TITLE = _('AI Assistant Discussion')

    def __init__(self, books: list[Metadata], parent: QWidget | None = None):
        self.books = books
        super().__init__(parent)

    def handle_chat_link(self, qurl: QUrl) -> bool:
        match qurl.host():
            case self.quick_action_hostname:
                name = from_hex_unicode(qurl.path().strip('/'))
                for ac in current_actions():
                    if ac.name == name:
                        self.activate_action(ac)
                        break
                return True
        return False

    def activate_action(self, action: Action) -> None:
        self.start_api_call(self.prompt_text_for_action(action))

    def choose_action_message(self) -> str:
        msg = '<p>'
        if len(self.books) > 1:
            msg += _('{0} books selected, starting with: <i>{1}</i>').format(len(self.books), self.books[0].title)
        else:
            msg += _('Selected book: <i>{}</i>').format(self.books[0].title)
        msg += self.quick_actions_as_html(current_actions())
        msg += '<p>' + _('Or, type a question to the AI below, for example:') + '<br>'
        msg += '<i>Discuss the literary influences in this book</i>'
        return msg
    ready_message = choose_action_message

    def get_language_instruction(self) -> str:
        if vprefs['llm_localized_results'] != 'always':
            return ''
        return self.language_instruction()

    def create_initial_messages(self, action_prompt: str, **kwargs: Any) -> Iterator[ChatMessage]:
        context_header = format_books_for_query(self.books)
        context_header += ' When you answer the questions use markdown formatting for the answers wherever possible.'
        if language_instruction := self.get_language_instruction():
            context_header += ' ' + language_instruction
        yield ChatMessage(context_header, type=ChatMessageType.system)
        yield ChatMessage(action_prompt)

    def prompt_text_for_action(self, action: Action) -> str:
        return action.prompt_text(self.books)


def develop():
    app = Application([])
    d = QDialog()
    l = QVBoxLayout(d)
    l.setContentsMargins(0, 0, 0, 0)

    llm = LLMPanel([Metadata('The Trials of Empire', ['Richard Swan'])], parent=d)
    l.addWidget(llm)
    d.exec()
    del app


if __name__ == '__main__':
    develop()
