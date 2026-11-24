#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import math
import textwrap
import unicodedata
from functools import partial
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from qt.core import (
    QAction,
    QApplication,
    QColor,
    QDialog,
    QIcon,
    QImage,
    QMainWindow,
    QMenu,
    QPainter,
    QPixmap,
    QPoint,
    QSize,
    Qt,
    QTextCursor,
    QToolButton,
    QUrl,
    pyqtSignal,
    qDrawShadeRect,
)

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.chardet import replace_encoding_declarations
from calibre.gui2 import error_dialog, open_url, qapplication_or_fail
from calibre.gui2.tweak_book import actions, current_container, dictionaries, editor_name, editor_toolbar_actions, editors, tprefs, update_mark_text_action
from calibre.gui2.tweak_book.editor import CLASS_ATTRIBUTE_PROPERTY, CSS_PROPERTY, LINK_PROPERTY, SPELL_PROPERTY, TAG_NAME_PROPERTY
from calibre.gui2.tweak_book.editor.help import help_url
from calibre.gui2.tweak_book.editor.text import TextEdit
from calibre.utils.icu import primary_sort_key, utf16_length
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from qt.core import QContextMenuEvent, QPalette, QToolBar, QWidget

    from calibre.gui2.tweak_book.completion.worker import Result
    from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
    from calibre.gui2.tweak_book.editor.text import RegexMatch, RegexPattern, SourceLineAddress
    from calibre.gui2.tweak_book.grammar import InlineGrammarChecker, InlineIssue, SentenceTarget
    from calibre.spell import DictionaryLocale
    from calibre.utils.config import JSONConfig


def create_icon(text: str, palette: QPalette | None = None, sz: int | None = None, divider: float = 2, fill: str | QColor | None = 'white') -> QIcon:
    if isinstance(fill, (str, bytes)):
        fill = QColor(fill)
    sz = sz or math.ceil(tprefs['toolbar_icon_size'] * qapplication_or_fail().devicePixelRatio())
    if palette is None:
        palette = QApplication.palette()
    img = QImage(sz, sz, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.Antialiasing)
    if fill is not None:
        qDrawShadeRect(p, img.rect(), palette, fill=fill, lineWidth=1, midLineWidth=1)
    f = p.font()
    f.setFamily('Liberation Sans'), f.setPixelSize(int(sz // divider)), f.setBold(True)
    p.setFont(f), p.setPen(QColor('#2271d5'))
    p.drawText(img.rect().adjusted(2, 2, -2, -2), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(QPixmap.fromImage(img))


def register_text_editor_actions(_reg: Callable[..., QAction], palette: QPalette) -> None:
    def reg(*args: object, **kw: Iterable[str]) -> QAction:
        ac = _reg(*args)
        for s in kw.get('syntaxes', ('format',)):
            editor_toolbar_actions[s][args[3]] = ac
        return ac

    ac = reg(
        'format-text-bold.png',
        _('&Bold'),
        ('format_text', 'bold'),
        'format-text-bold',
        'Ctrl+B',
        _('Make the selected text bold'),
    )
    ac.setToolTip(_('<h3>Bold</h3>Make the selected text bold'))
    ac = reg(
        'format-text-italic.png',
        _('&Italic'),
        ('format_text', 'italic'),
        'format-text-italic',
        'Ctrl+I',
        _('Make the selected text italic'),
    )
    ac.setToolTip(_('<h3>Italic</h3>Make the selected text italic'))
    ac = reg(
        'format-text-underline.png',
        _('&Underline'),
        ('format_text', 'underline'),
        'format-text-underline',
        (),
        _('Underline the selected text'),
    )
    ac.setToolTip(_('<h3>Underline</h3>Underline the selected text'))
    ac = reg(
        'format-text-strikethrough.png',
        _('&Strikethrough'),
        ('format_text', 'strikethrough'),
        'format-text-strikethrough',
        (),
        _('Draw a line through the selected text'),
    )
    ac.setToolTip(_('<h3>Strikethrough</h3>Draw a line through the selected text'))
    ac = reg(
        'format-text-superscript.png',
        _('&Superscript'),
        ('format_text', 'superscript'),
        'format-text-superscript',
        (),
        _('Make the selected text a superscript'),
    )
    ac.setToolTip(_('<h3>Superscript</h3>Set the selected text slightly smaller and above the normal line'))
    ac = reg(
        'format-text-subscript.png',
        _('&Subscript'),
        ('format_text', 'subscript'),
        'format-text-subscript',
        (),
        _('Make the selected text a subscript'),
    )
    ac.setToolTip(_('<h3>Subscript</h3>Set the selected text slightly smaller and below the normal line'))
    ac = reg('format-text-color.png', _('&Color'), ('format_text', 'color'), 'format-text-color', (), _('Change text color'))
    ac.setToolTip(_('<h3>Color</h3>Change the color of the selected text'))
    ac = reg(
        'format-fill-color.png',
        _('&Background color'),
        ('format_text', 'background-color'),
        'format-text-background-color',
        (),
        _('Change background color of text'),
    )
    ac.setToolTip(_('<h3>Background color</h3>Change the background color of the selected text'))
    ac = reg(
        'format-justify-left.png',
        _('Align &left'),
        ('format_text', 'justify_left'),
        'format-text-justify-left',
        (),
        _('Align left'),
    )
    ac.setToolTip(_('<h3>Align left</h3>Align the paragraph to the left'))
    ac = reg(
        'format-justify-center.png',
        _('&Center'),
        ('format_text', 'justify_center'),
        'format-text-justify-center',
        (),
        _('Center'),
    )
    ac.setToolTip(_('<h3>Center</h3>Center the paragraph'))
    ac = reg(
        'format-justify-right.png',
        _('Align &right'),
        ('format_text', 'justify_right'),
        'format-text-justify-right',
        (),
        _('Align right'),
    )
    ac.setToolTip(_('<h3>Align right</h3>Align the paragraph to the right'))
    ac = reg(
        'format-justify-fill.png',
        _('&Justify'),
        ('format_text', 'justify_justify'),
        'format-text-justify-fill',
        (),
        _('Justify'),
    )
    ac.setToolTip(_('<h3>Justify</h3>Align the paragraph to both the left and right margins'))

    ac = reg(
        'sort.png',
        _('&Sort style rules'),
        ('sort_css',),
        'editor-sort-css',
        (),
        _('Sort the style rules'),
        syntaxes=('css',),
    )
    ac = reg(
        'view-image.png',
        _('&Insert image'),
        ('insert_resource', 'image'),
        'insert-image',
        (),
        _('Insert an image into the text'),
        syntaxes=('html', 'css'),
    )
    ac.setToolTip(_('<h3>Insert image</h3>Insert an image into the text'))

    ac = reg(
        'insert-link.png',
        _('Insert &hyperlink'),
        ('insert_hyperlink',),
        'insert-hyperlink',
        (),
        _('Insert hyperlink'),
        syntaxes=('html',),
    )
    ac.setToolTip(_('<h3>Insert hyperlink</h3>Insert a hyperlink into the text'))

    ac = reg(
        create_icon('/*', divider=1, fill=None),
        _('Smart &comment'),
        ('smart_comment',),
        'editor-smart-comment',
        ('Ctrl+`',),
        _('Smart comment (toggle block comments)'),
        syntaxes=(),
    )
    ac.setToolTip(
        _(
            '<h3>Smart comment</h3>Comment or uncomment text<br><br>'
            'If the cursor is inside an existing block comment, uncomment it, otherwise comment out the selected text.'
        )
    )

    for i, name in enumerate(('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p')):
        text = ('&' + name) if name == 'p' else (name[0] + '&' + name[1])
        desc = _('Convert the paragraph to &lt;%s&gt;') % name
        ac = reg(
            create_icon(name),
            text,
            ('rename_block_tag', name),
            'rename-block-tag-' + name,
            f'Ctrl+{i + 1}',
            desc,
            syntaxes=(),
        )
        ac.setToolTip(desc)

    for transform, text in [
        ('upper', _('&Upper case')),
        ('lower', _('&Lower case')),
        ('swap', _('&Swap case')),
        ('title', _('&Title case')),
        ('capitalize', _('&Capitalize')),
    ]:
        desc = _('Change the case of the selected text: %s') % text
        ac = reg(None, text, ('change_case', transform), 'transform-case-' + transform, (), desc, syntaxes=())
        ac.setToolTip(desc)

    ac = reg(
        'code.png',
        _('Insert &tag'),
        ('insert_tag',),
        'insert-tag',
        ('Ctrl+<'),
        _('Insert tag'),
        syntaxes=('html', 'xml'),
    )
    ac.setToolTip(_('<h3>Insert tag</h3>Insert a tag, if some text is selected the tag will be inserted around the selected text'))

    ac = reg(
        'trash.png',
        _('Remove &tag'),
        ('remove_tag',),
        'remove-tag',
        ('Ctrl+>'),
        _('Remove tag'),
        syntaxes=('html', 'xml'),
    )
    ac.setToolTip(_('<h3>Remove tag</h3>Remove the currently highlighted tag'))

    ac = reg(
        'split.png',
        _('&Split tag'),
        ('split_tag',),
        'split-tag',
        ('Ctrl+Alt+>'),
        _('Split current tag'),
        syntaxes=('html', 'xml'),
    )
    ac.setToolTip(_('<h3>Split tag</h3>Split the current tag at the cursor position'))

    editor_toolbar_actions['html']['fix-html-current'] = actions['fix-html-current']
    for s in ('xml', 'html', 'css'):
        editor_toolbar_actions[s]['pretty-current'] = actions['pretty-current']
    editor_toolbar_actions['html']['change-paragraph'] = actions['change-paragraph'] = QAction(
        QIcon.ic('format-text-heading.png'), _('Change paragraph to heading'), ac.parent()
    )


class Editor(QMainWindow):
    # Literal so that the type checker can use it to tell the editor types apart
    has_line_numbers: ClassVar[Literal[True]] = True

    modification_state_changed = pyqtSignal(object)
    undo_redo_state_changed = pyqtSignal(object, object)
    copy_available_state_changed = pyqtSignal(object)
    data_changed = pyqtSignal(object)
    cursor_position_changed = pyqtSignal()
    word_ignored = pyqtSignal(object, object)
    link_clicked = pyqtSignal(object)
    class_clicked = pyqtSignal(object)
    rename_class = pyqtSignal(object)
    smart_highlighting_updated = pyqtSignal()

    def __init__(self, syntax: str, parent: QWidget | None = None) -> None:
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)
        self.is_synced_to_container = False
        self.syntax = syntax
        self.editor = TextEdit(self)
        if syntax == 'html':
            from calibre.gui2.tweak_book.grammar import InlineGrammarChecker

            self.editor.grammar_checker = InlineGrammarChecker(self.editor)
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.setCentralWidget(self.editor)
        self.create_toolbars()
        self.undo_available = False
        self.redo_available = False
        self.copy_available = self.cut_available = False
        self.editor.modificationChanged.connect(self._modification_state_changed)
        self.editor.undoAvailable.connect(self._undo_available)
        self.editor.redoAvailable.connect(self._redo_available)
        self.editor.textChanged.connect(self._data_changed)
        self.editor.copyAvailable.connect(self._copy_available)
        self.editor.cursorPositionChanged.connect(self._cursor_position_changed)
        self.editor.link_clicked.connect(self.link_clicked)
        self.editor.class_clicked.connect(self.class_clicked)
        self.editor.smart_highlighting_updated.connect(self.smart_highlighting_updated)

    @property
    def current_line(self) -> int:
        return self.editor.textCursor().blockNumber()

    @current_line.setter
    def current_line(self, val: int) -> None:
        self.editor.go_to_line(val)

    @property
    def current_editing_state(self) -> dict[str, tuple[int, int]]:
        c = self.editor.textCursor()
        return {'cursor': (c.anchor(), c.position())}

    @current_editing_state.setter
    def current_editing_state(self, val: dict[str, tuple[int, int]]) -> None:
        anchor, position = val.get('cursor', (None, None))
        if anchor is not None and position is not None:
            c = self.editor.textCursor()
            c.setPosition(anchor), c.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
            self.editor.setTextCursor(c)

    def current_tag(self, for_position_sync: bool = True) -> SourceLineAddress:
        return self.editor.current_tag(for_position_sync=for_position_sync)

    @property
    def highlighter(self) -> SyntaxHighlighter:
        return self.editor.highlighter

    @property
    def number_of_lines(self) -> int:
        return self.editor.blockCount()

    @property
    def data(self) -> bytes:
        ans = self.get_raw_data()
        ans, changed = replace_encoding_declarations(ans, enc='utf-8', limit=4 * 1024)
        if changed:
            self.data = ans
        return ans.encode('utf-8')

    @data.setter
    def data(self, val: str | bytes) -> None:
        self.editor.load_text(val, syntax=self.syntax, doc_name=editor_name(self))

    def init_from_template(self, template: str | bytes) -> None:
        self.editor.load_text(template, syntax=self.syntax, process_template=True, doc_name=editor_name(self))

    def change_document_name(self, newname: str) -> None:
        self.editor.change_document_name(newname)
        self.editor.completion_doc_name = newname

    def get_raw_data(self) -> str:
        # The EPUB spec requires NFC normalization, see section 1.3.6 of
        # http://www.idpf.org/epub/20/spec/OPS_2.0.1_draft.htm
        return unicodedata.normalize('NFC', str(self.editor.toPlainText()).rstrip('\0'))

    def replace_data(self, raw: str | bytes, only_if_different: bool = True) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        current = self.get_raw_data() if only_if_different else False
        if current != raw:
            self.editor.replace_text(raw)

    def apply_settings(self, prefs: JSONConfig | None = None, dictionaries_changed: bool = False) -> None:
        self.editor.apply_settings(prefs=None, dictionaries_changed=dictionaries_changed)

    def set_focus(self) -> None:
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def action_triggered(self, action: Sequence[str]) -> None:
        action, args = action[0], action[1:]
        func = getattr(self.editor, action)
        func(*args)

    def insert_image(self, href: str, fullpage: bool = False, preserve_aspect_ratio: bool = False, width: int = -1, height: int = -1) -> None:
        self.editor.insert_image(href, fullpage=fullpage, preserve_aspect_ratio=preserve_aspect_ratio, width=width, height=height)

    def insert_hyperlink(self, href: str, text: str, template: str | None = None) -> None:
        self.editor.insert_hyperlink(href, text, template=template)

    def _build_insert_tag_button_menu(self) -> None:
        m = self.insert_tag_menu
        m.clear()
        names = tprefs['insert_tag_mru']
        for name in names:
            m.addAction(name, partial(self.insert_tag, name))
        m.addSeparator()
        m.addAction(_('Manage the entries in this menu'), self.manage_insert_tags)

    def insert_tag(self, name: str) -> None:
        self.editor.insert_tag(name)
        mru = tprefs['insert_tag_mru']
        try:
            mru.remove(name)
        except ValueError:
            pass
        mru.insert(0, name)
        tprefs['insert_tag_mru'] = mru
        self._build_insert_tag_button_menu()

    def manage_insert_tags(self) -> None:
        from calibre.gui2.tweak_book.widgets import ManageTagList

        d = ManageTagList(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self._build_insert_tag_button_menu()

    def set_request_completion(self, callback: Callable[..., int | None] | None = None, doc_name: str | None = None) -> None:
        self.editor.request_completion = callback
        self.editor.completion_doc_name = doc_name

    def handle_completion_result(self, result: Result) -> None:
        return self.editor.handle_completion_result(result)

    def undo(self) -> None:
        self.editor.undo()

    def redo(self) -> None:
        self.editor.redo()

    @property
    def selected_text(self) -> str:
        return self.editor.selected_text

    def get_smart_selection(self, update: bool = True) -> str:
        return self.editor.smarts.get_smart_selection(self.editor, update=update)

    # Search and replace {{{
    def mark_selected_text(self) -> None:
        self.editor.mark_selected_text()

    def find(  # ty: ignore[incompatible-method-override]
        self, exp: RegexPattern, wrap: bool = False, marked: bool = False, complete: bool = False, save_match: str | None = None
    ) -> bool:
        return self.editor.find(exp, wrap=wrap, marked=marked, complete=complete, save_match=save_match)

    def find_text(self, pat: RegexPattern, wrap: bool = False, complete: bool = False) -> bool:
        return self.editor.find_text(pat, wrap=wrap, complete=complete)

    def find_spell_word(self, original_words: Sequence[str], lang: str, from_cursor: bool = True, center_on_cursor: bool = True) -> bool | None:
        return self.editor.find_spell_word(original_words, lang, from_cursor=from_cursor, center_on_cursor=center_on_cursor)

    def replace(self, pat: RegexPattern, template: str | Callable[[RegexMatch], str], saved_match: str | None = 'gui') -> bool:
        return self.editor.replace(pat, template, saved_match=saved_match)

    def all_in_marked(self, pat: RegexPattern, template: str | Callable[[RegexMatch], str] | None = None) -> int:
        return self.editor.all_in_marked(pat, template=template)

    def go_to_anchor(self, anchor: str | object) -> bool:
        return self.editor.go_to_anchor(anchor)

    # }}}

    @property
    def has_marked_text(self) -> bool:
        return self.editor.current_search_mark is not None

    @property
    def is_modified(self) -> bool:
        return self.editor.is_modified

    @is_modified.setter
    def is_modified(self, val: bool) -> None:
        self.editor.is_modified = val

    def create_toolbars(self) -> None:
        self.action_bar = b = self.addToolBar(_('Edit actions tool bar'))
        assert b is not None
        b.setObjectName('action_bar')  # Needed for saveState
        self.tools_bar = b = self.addToolBar(_('Editor tools'))
        assert b is not None
        b.setObjectName('tools_bar')
        self.bars = [self.action_bar, self.tools_bar]
        if self.syntax == 'html':
            self.format_bar = b = self.addToolBar(_('Format text'))
            assert b is not None
            b.setObjectName('html_format_bar')
            self.bars.append(self.format_bar)
        self.insert_tag_menu = QMenu(self)
        self.populate_toolbars()
        for x in self.bars:
            assert x is not None
            x.setFloatable(False)
            x.topLevelChanged.connect(self.toolbar_floated)
            x.setIconSize(QSize(tprefs['toolbar_icon_size'], tprefs['toolbar_icon_size']))

    def toolbar_floated(self, floating: bool) -> None:
        if not floating:
            self.save_state()
            for ed in editors.values():
                if ed is not self:
                    ed.restore_state()

    def save_state(self) -> None:
        for bar in self.bars:
            assert bar is not None
            if bar.isFloating():
                return
        tprefs[f'{self.syntax}-editor-state'] = bytearray(self.saveState())

    def restore_state(self) -> None:
        state = tprefs.get(f'{self.syntax}-editor-state', None)
        if state is not None:
            self.restoreState(state)
        for bar in self.bars:
            assert bar is not None
            bar.setVisible(len(bar.actions()) > 0)

    def populate_toolbars(self) -> None:
        assert self.action_bar is not None
        assert self.tools_bar is not None
        self.action_bar.clear(), self.tools_bar.clear()

        def add_action(name: str | None, bar: QToolBar) -> None:
            if name is None:
                bar.addSeparator()
                return
            try:
                ac = actions[name]
            except KeyError:
                if DEBUG:
                    prints(f'Unknown editor tool: {name!r}')
                return
            bar.addAction(ac)
            if name == 'insert-tag':
                # For some unknown reason this button is occasionally a
                # QPushButton instead of a QToolButton, both have the methods used below
                w = cast('QToolButton', bar.widgetForAction(ac))
                if hasattr(w, 'setPopupMode'):
                    # For some unknown reason this button is occasionally a
                    # QPushButton instead of a QToolButton
                    w.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                w.setMenu(self.insert_tag_menu)
                w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                w.customContextMenuRequested.connect(w.showMenu)
                self._build_insert_tag_button_menu()
            elif name == 'change-paragraph':
                m = QMenu()
                setattr(ac, 'm', m)
                ac.setMenu(m)
                ch = cast('QToolButton', bar.widgetForAction(ac))
                if hasattr(ch, 'setPopupMode'):
                    # For some unknown reason this button is occasionally a
                    # QPushButton instead of a QToolButton
                    ch.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                for name in tuple(f'h{d}' for d in range(1, 7)) + ('p',):
                    m.addAction(actions[f'rename-block-tag-{name}'])

        for name in tprefs.get('editor_common_toolbar', ()):
            add_action(name, self.action_bar)

        for name in tprefs.get(f'editor_{self.syntax}_toolbar', ()):
            add_action(name, self.tools_bar)

        if self.syntax == 'html':
            assert self.format_bar is not None
            self.format_bar.clear()
            for name in tprefs['editor_format_toolbar']:
                add_action(name, self.format_bar)
        self.restore_state()

    def break_cycles(self) -> None:
        for x in (
            'modification_state_changed',
            'word_ignored',
            'link_clicked',
            'class_clicked',
            'smart_highlighting_updated',
        ):
            try:
                getattr(self, x).disconnect()
            except TypeError:
                pass  # in case this signal was never connected
        self.undo_redo_state_changed.disconnect()
        self.copy_available_state_changed.disconnect()
        self.cursor_position_changed.disconnect()
        self.data_changed.disconnect()
        self.editor.undoAvailable.disconnect()
        self.editor.redoAvailable.disconnect()
        self.editor.modificationChanged.disconnect()
        self.editor.textChanged.disconnect()
        self.editor.copyAvailable.disconnect()
        self.editor.cursorPositionChanged.disconnect()
        self.editor.link_clicked.disconnect()
        self.editor.class_clicked.disconnect()
        self.editor.smart_highlighting_updated.disconnect()
        self.editor.setPlainText('')
        setattr(self.editor, 'smarts', None)
        self.editor.request_completion = None

    def _modification_state_changed(self) -> None:
        self.is_synced_to_container = self.is_modified
        self.modification_state_changed.emit(self.is_modified)

    def _data_changed(self) -> None:
        self.is_synced_to_container = False
        self.data_changed.emit(self)

    def _undo_available(self, available: bool) -> None:
        self.undo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _redo_available(self, available: bool) -> None:
        self.redo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _copy_available(self, available: bool) -> None:
        self.copy_available = self.cut_available = available
        self.copy_available_state_changed.emit(available)

    def _cursor_position_changed(self, *args: object) -> None:
        self.cursor_position_changed.emit()

    @property
    def cursor_position(self) -> tuple[int, int, str]:
        c = self.editor.textCursor()
        char = ''
        col = c.positionInBlock()
        if not c.atStart():
            c.clearSelection()
            c.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.KeepAnchor)
            char = str(c.selectedText()).rstrip('\0')
        return (c.blockNumber() + 1, col, char)

    def cut(self) -> None:
        self.editor.cut()

    def copy(self) -> None:
        self.editor.copy()

    def go_to_line(self, line: int, col: int | None = None) -> None:
        self.editor.go_to_line(line, col=col)

    def paste(self) -> int | None:
        if not self.editor.canPaste():
            return error_dialog(self, _('No text'), _('There is no suitable text in the clipboard to paste.'), show=True)
        self.editor.paste()

    def contextMenuEvent(self, event: QContextMenuEvent | None) -> None:
        if event is not None:
            event.ignore()

    def fix_html(self) -> bool:
        if self.syntax == 'html':
            from calibre.ebooks.oeb.polish.pretty import fix_html

            self.editor.replace_text(fix_html(current_container(), str(self.editor.toPlainText())).decode('utf-8'))
            return True
        return False

    def pretty_print(self, name: str) -> bool:
        from calibre.ebooks.oeb.polish.pretty import pretty_css, pretty_html, pretty_xml

        if self.syntax in {'css', 'html', 'xml'}:
            func = {'css': pretty_css, 'xml': pretty_xml}.get(self.syntax, pretty_html)
            original_text = str(self.editor.toPlainText())
            prettied_text = func(current_container(), name, original_text).decode('utf-8')
            if original_text != prettied_text:
                self.editor.replace_text(prettied_text)
            return True
        return False

    def show_context_menu(self, pos: QPoint) -> None:
        m = QMenu(self)
        m.setToolTipsVisible(True)
        a = m.addAction
        c = self.editor.cursorForPosition(pos)
        origc = QTextCursor(c)
        current_cursor = self.editor.textCursor()
        if (gc := self.editor.grammar_checker) is not None:
            gpos = c.position()
            if (gi := gc.issue_at(gpos) or (gc.issue_at(gpos - 1) if gpos > 0 else None)) is not None:
                self.add_grammar_actions(m, gc, gi)
            if gc.enabled and gc.missing_languages:
                self.add_grammar_download_actions(m, gc)
            if (target := gc.sentence_target(gpos)) is not None:
                vp = self.editor.viewport()
                assert vp is not None
                self.add_rewrite_action(m, gc, target, vp.mapToGlobal(pos))
        r = self.editor.syntax_range_for_cursor(c)
        origr = self.editor.syntax_range_for_point(pos)
        if (r is None or not r.format.property(SPELL_PROPERTY)) and c.positionInBlock() > 0 and not current_cursor.hasSelection():
            c.setPosition(c.position() - 1)
            r = self.editor.syntax_range_for_cursor(c)

        if r is not None and r.format.property(SPELL_PROPERTY):
            word = self.editor.text_for_range(c.block(), r)
            locale = self.editor.spellcheck_locale_for_cursor(c)
            orig_pos = c.position()
            c.setPosition(orig_pos - utf16_length(word))
            found = False
            self.editor.setTextCursor(c)
            if locale and self.editor.find_spell_word([word], locale.langcode, center_on_cursor=False):
                found = True
                fc = self.editor.textCursor()
                if fc.position() < c.position():
                    self.editor.find_spell_word([word], locale.langcode, center_on_cursor=False)
            spell_cursor = self.editor.textCursor()
            if current_cursor.hasSelection():
                # Restore the current cursor so that any selection is preserved
                # for the change case actions
                self.editor.setTextCursor(current_cursor)
            if found and locale is not None:  # found is only True if locale is not None
                suggestions = dictionaries.suggestions(word, locale)[:7]
                if suggestions:
                    for suggestion in suggestions:
                        ac = m.addAction(suggestion, partial(self.editor.simple_replace, suggestion, cursor=spell_cursor))
                        assert ac is not None
                        f = ac.font()
                        f.setBold(True), ac.setFont(f)
                    m.addSeparator()
                m.addAction(actions['spell-next'])
                m.addAction(_('Ignore this word'), partial(self._nuke_word, None, word, locale))
                dics = dictionaries.active_user_dictionaries
                if len(dics) > 0:
                    if len(dics) == 1:
                        m.addAction(
                            _('Add this word to the dictionary: {0}').format(dics[0].name),
                            partial(self._nuke_word, dics[0].name, word, locale),
                        )
                    else:
                        ac = m.addAction(_('Add this word to the dictionary'))
                        assert ac is not None
                        dmenu = QMenu(m)
                        ac.setMenu(dmenu)
                        for dic in sorted(dics, key=lambda x: primary_sort_key(x.name)):
                            dmenu.addAction(dic.name, partial(self._nuke_word, dic.name, word, locale))
                m.addSeparator()

        if origr is not None and origr.format.property(LINK_PROPERTY):
            href = self.editor.text_for_range(origc.block(), origr)
            m.addAction(_('Open %s') % href, partial(self.link_clicked.emit, href))

        if origr is not None and origr.format.property(CLASS_ATTRIBUTE_PROPERTY):
            cls = self.editor.class_for_position(pos)
            if cls:
                class_name = cls['class']
                m.addAction(_('Rename the class {}').format(class_name), partial(self.rename_class.emit, class_name))

        if origr is not None and (origr.format.property(TAG_NAME_PROPERTY) or origr.format.property(CSS_PROPERTY)):
            word = self.editor.text_for_range(origc.block(), origr)
            item_type = 'tag_name' if origr.format.property(TAG_NAME_PROPERTY) else 'css_property'
            doc_name = self.editor.highlighter.doc_name
            assert doc_name is not None
            url = help_url(word, item_type, doc_name, extra_data=current_container().opf_version)
            if url is not None:
                m.addAction(_('Show help for: %s') % word, partial(open_url, url))

        for x in ('undo', 'redo'):
            ac = actions[f'editor-{x}']
            if ac.isEnabled():
                a(ac)
        m.addSeparator()
        for x in ('cut', 'copy', 'paste'):
            ac = actions['editor-' + x]
            if ac.isEnabled():
                a(ac)
        m.addSeparator()
        m.addAction(_('&Select all'), self.editor.select_all)
        if self.selected_text or self.has_marked_text:
            update_mark_text_action(self)
            m.addAction(actions['mark-selected-text'])
        if self.syntax != 'css' and actions['editor-cut'].isEnabled():
            cm = QMenu(_('C&hange case'), m)
            for ac in 'upper lower swap title capitalize'.split():
                cm.addAction(actions['transform-case-' + ac])
            m.addMenu(cm)
        if self.syntax == 'html':
            m.addAction(actions['multisplit'])
        viewport = self.editor.viewport()
        assert viewport is not None
        m.exec(viewport.mapToGlobal(pos))

    def add_grammar_actions(self, m: QMenu, checker: InlineGrammarChecker, gi: InlineIssue) -> None:
        from calibre.gui2.tweak_book.grammar import MAX_CONTEXT_MENU_REPLACEMENTS, grammar_service, rule_description

        issue = gi.issue
        desc = rule_description(issue)
        ac = m.addAction(QIcon.ic('grammar-check.png'), textwrap.shorten(desc, 60, placeholder='…'))
        assert ac is not None
        ac.setEnabled(False)
        ac.setToolTip(issue.message)
        for r in issue.replacements[:MAX_CONTEXT_MENU_REPLACEMENTS]:
            ac = m.addAction(r or _('Remove the text'), partial(checker.apply_replacement, gi, r))
            assert ac is not None
            f = ac.font()
            f.setBold(True), ac.setFont(f)
        m.addSeparator()
        m.addAction(actions['grammar-next'])
        service = grammar_service()
        m.addAction(_('Ignore this issue'), partial(service.ignore, gi.key))
        ac = m.addAction(_('Disable this rule'), partial(service.disable_rule, issue.rule_id, desc))
        assert ac is not None
        ac.setToolTip(_('Stop checking for this kind of issue. Disabled rules can be enabled again in the Check grammar tool.'))
        if issue.url:
            m.addAction(_('Explain this issue'), partial(open_url, QUrl(issue.url)))
        m.addSeparator()

    def add_rewrite_action(self, m: QMenu, checker: InlineGrammarChecker, target: SentenceTarget, pos: QPoint) -> None:
        from calibre.gui2.tweak_book.grammar import show_rewrite_popup

        ac = actions['grammar-suggest']
        m.addAction(ac.icon(), ac.text(), partial(show_rewrite_popup, self.editor, target, checker.apply_suggestion, pos))
        m.addSeparator()

    def add_grammar_download_actions(self, m: QMenu, checker: InlineGrammarChecker) -> None:
        from calibre.gui2.tweak_book.grammar import ensure_language_data, language_name

        for lang in sorted(checker.missing_languages, key=language_name):
            m.addAction(
                QIcon.ic('grammar-check.png'),
                _('Download data for checking the grammar of {}').format(language_name(lang)),
                partial(ensure_language_data, self, lang),
            )
        m.addSeparator()

    def goto_sourceline(self, sourceline: int | None, tags: list[str], attribute: str | None = None) -> bool:
        return self.editor.goto_sourceline(sourceline, tags, attribute=attribute)

    def goto_css_rule(self, rule_address: Sequence[int], sourceline_address: tuple[int, list[str]] | None = None) -> None:
        return self.editor.goto_css_rule(rule_address, sourceline_address=sourceline_address)

    def get_tag_contents(self) -> str | None:
        return self.editor.get_tag_contents()

    def _nuke_word(self, dic: str | None, word: str, locale: DictionaryLocale) -> None:
        if dic is None:
            dictionaries.ignore_word(word, locale)
        else:
            dictionaries.add_to_user_dictionary(dic, word, locale)
        self.word_ignored.emit(word, locale)


def launch_editor(path_to_edit: str, path_is_raw: bool = False, syntax: str = 'html', callback: Callable[[Editor], object] | None = None) -> None:
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book import dictionaries
    from calibre.gui2.tweak_book.editor.syntax.html import refresh_spell_check_status
    from calibre.gui2.tweak_book.main import option_parser
    from calibre.gui2.tweak_book.ui import Main

    dictionaries.initialize()
    refresh_spell_check_status()
    opts, args = option_parser().parse_args([])
    app = Application([])
    # Create the actions that are placed into the editors toolbars
    main = Main(opts)  # ruff: ignore[unused-variable]
    if path_is_raw:
        raw = path_to_edit
    else:
        with open(path_to_edit, 'rb') as f:
            raw = f.read().decode('utf-8')
        ext = path_to_edit.rpartition('.')[-1].lower()
        if ext in ('html', 'htm', 'xhtml', 'xhtm'):
            syntax = 'html'
        elif ext == 'css':
            syntax = 'css'
    t = Editor(syntax)
    t.data = raw
    if callback is not None:
        callback(t)
    t.show()
    app.exec()
