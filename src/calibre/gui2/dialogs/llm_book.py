#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from qt.core import QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QSize, Qt, QUrl, QVBoxLayout, QWidget, pyqtSignal

from calibre.ai import ChatMessage, ChatMessageType
from calibre.db.cache import Cache
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import Application, gprefs
from calibre.gui2.llm import ActionData, ConverseWidget, LLMActionsSettingsWidget, LLMSettingsDialogBase, LocalisedResults
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key
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
    db = get_current_db()
    ans = set(db.pref('llm-book-allowed-custom-fields') or ())
    return set(gprefs.get('llm-book-allowed-standard-fields') or ()) | ans


class Action(ActionData):

    def prompt_text(self, books: list[Metadata]) -> str:
        pt = self.prompt_template
        return pt.format(
            books_word='book' if len(books) < 2 else 'books',
            is_are='is' if len(books) < 2 else 'are',
            title=books[0].title, authors=books[0].format_authors(), series=books[0].series or '',
        )


@lru_cache(2)
def default_actions() -> tuple[Action, ...]:
    return (
        Action('summarize', _('Summarize'), 'Provide a concise summary of the previously described {books_word}.'),
        Action('chapters', _('Chapters'), 'Provide a chapter by chapter summary of the previously described {books_word}.'),
        Action('read_next', _('Read next'), 'Suggest some good books to read after the previously described {books_word}.'),
        Action('universe', _('Universe'), 'Describe the fictional universe the previously described {books_word} {is_are} set in.'
               ' Outline major plots, themes and characters in the universe.'),
        Action('series', _('Series'), 'Give the series the previously described {books_word} {is_are} in.'
               ' List all the books in the series, in both published and internal chronological order.'
               ' Also describe any prominent spin-off series.')
    )


def read_next_action() -> Action:
    for ac in default_actions():
        if ac.name == 'read_next':
            return ac
    raise KeyError('No read next action could be found')


def current_actions(include_disabled=False) -> Iterator[Action]:
    p = gprefs.get('llm_book_quick_actions') or {}
    return Action.unserialize(p, default_actions(), include_disabled)


class LLMSettingsWidget(LLMActionsSettingsWidget):

    action_edit_help_text = '<p>' + _(
        'The prompt is a template. The expression {0} will be replaced by "book"'
        ' when there is only a single book being discussed and "books" otherwise.'
        ' Similarly {1} becomes "is" or "are", as needed. {2}, {3}, {4} are replaced '
        ' by the title, authors and series of the first book, respectively.'
    ).format('{books_word}', '{is_are}', '{title}', '{authors}', '{series}')

    def get_actions_from_prefs(self) -> Iterator[ActionData]:
        yield from current_actions(include_disabled=True)

    def set_actions_in_prefs(self, s: dict[str, Any]) -> None:
        gprefs.set('llm_book_quick_actions', s)

    def create_custom_widgets(self) -> Iterator[str, QWidget]:
        yield '', LocalisedResults()


def get_current_db() -> Cache:
    if db := getattr(get_current_db, 'ans', None):
        return db.new_api
    return get_gui().current_db.new_api


class MetadataSettings(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        la = QLabel(_('Select which metadata fields to send to the AI from the selected books. Note that title and authors are always sent.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.list_widget = lw = QListWidget(self)
        lw.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        lw.itemClicked.connect(self.toggle_item)
        l.addWidget(lw)
        db = get_current_db()
        fm = db.field_metadata
        allowed = get_allowed_fields()
        for field_name in sorted(fm.displayable_field_keys(), key=lambda n: primary_sort_key(fm[n]['label'])):
            if field_name in ('title', 'authors', 'author_sort', 'sort', 'id', 'uuid'):
                continue
            fd = fm[field_name]
            item = QListWidgetItem(fd['name'], lw)
            item.setToolTip(field_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if field_name in allowed else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, field_name)
        bb = QDialogButtonBox(self)
        bb.addButton(_('Select &all'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.select_all)
        bb.addButton(_('Select &none'), QDialogButtonBox.ButtonRole.ActionRole).clicked.connect(self.select_none)
        l.addWidget(bb)

    def __iter__(self):
        lw = self.list_widget
        return (lw.item(r) for r in range(lw.count()))

    def select_all(self):
        for item in self:
            item.setCheckState(Qt.CheckState.Checked)

    def select_none(self):
        for item in self:
            item.setCheckState(Qt.CheckState.Unchecked)

    def toggle_item(self, item):
        item.setCheckState(
            Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)

    def commit(self) -> bool:
        allowed_standard = set()
        allowed_custom = set()
        for item in self:
            if item.checkState() == Qt.CheckState.Checked:
                f = item.data(Qt.ItemDataRole.UserRole)
                if f.startswith('#'):
                    allowed_custom.add(f)
                else:
                    allowed_standard.add(f)
        gprefs.set('llm-book-allowed-standard-fields', sorted(allowed_standard))
        db = get_current_db()
        db.set_pref('llm-book-allowed-custom-fields', sorted(allowed_custom))
        return True


class LLMSettingsDialog(LLMSettingsDialogBase):

    def __init__(self, parent=None):
        super().__init__(title=_('AI Settings'), name='llm-book-settings-dialog', prefs=gprefs, parent=parent)

    def custom_tabs(self) -> Iterator[str, str, QWidget]:
        yield 'config.png', _('&Actions'), LLMSettingsWidget(self)
        yield 'metadata.png', _('&Metadata'), MetadataSettings(self)


class LLMPanel(ConverseWidget):
    NOTE_TITLE = _('AI Assistant Discussion')
    close_requested = pyqtSignal()

    def __init__(self, books: list[Metadata], parent: QWidget | None = None):
        self.books = books
        super().__init__(parent, add_close_button=True)
        self.close_requested.connect(self.close_requested)

    def settings_dialog(self) -> QDialog:
        return LLMSettingsDialog(self)

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

    def create_initial_messages(self, action_prompt: str, **kwargs: Any) -> Iterator[ChatMessage]:
        context_header = format_books_for_query(self.books)
        context_header += ' When you answer the questions use markdown formatting for the answers wherever possible.'
        if language_instruction := self.get_language_instruction():
            context_header += ' ' + language_instruction
        yield ChatMessage(context_header, type=ChatMessageType.system)
        yield ChatMessage(action_prompt)

    def prompt_text_for_action(self, action: Action) -> str:
        return action.prompt_text(self.books)


class LLMBookDialog(Dialog):

    def __init__(self, books: list[Metadata], parent: QWidget | None = None):
        self.books = books
        super().__init__(
            name='llm-book-dialog', title=_('Ask AI about {}').format(books[0].title) if len(books) < 2 else _(
                'Ask AI about {} books').format(len(books)),
            parent=parent, default_buttons=QDialogButtonBox.StandardButton.Close)

    def setup_ui(self):
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.llm = llm = LLMPanel(self.books, parent=self)
        self.llm.close_requested.connect(self.accept)
        l.addWidget(llm)
        self.bb.setVisible(False)

    def sizeHint(self):
        return QSize(600, 750)


def develop():
    from calibre.library import db
    get_current_db.ans = db()
    app = Application([])
    LLMBookDialog([Metadata('The Trials of Empire', ['Richard Swan'])]).exec()
    del app


if __name__ == '__main__':
    develop()
