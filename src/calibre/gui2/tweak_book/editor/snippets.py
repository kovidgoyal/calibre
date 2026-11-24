#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

import copy
import re
import weakref
from collections import OrderedDict
from itertools import groupby
from operator import attrgetter, itemgetter
from typing import TYPE_CHECKING, Literal, NamedTuple, Self, cast, overload

from qt.core import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QObject,
    QPushButton,
    QSize,
    QStackedLayout,
    Qt,
    QTextCursor,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from calibre.constants import ismacos
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor import all_text_syntaxes
from calibre.gui2.tweak_book.editor.smarts.utils import get_text_before_cursor
from calibre.gui2.tweak_book.widgets import Dialog, PlainTextEdit
from calibre.utils.config import JSONConfig
from calibre.utils.icu import string_length as strlen
from calibre.utils.localization import _, localize_user_manual_link

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence
    from typing import TypedDict

    from qt.core import QKeyEvent

    from calibre.gui2.tweak_book.editor.text import TextEdit

    class Snippet(TypedDict, total=False):
        description: str
        template: str
        trigger: str
        syntaxes: Collection[str]

    SnippetsFunc = Callable[[], Iterable[tuple['SnipKey', Snippet]]]


def string_length(x: object) -> int:
    return strlen(str(x))  # Needed on narrow python builds, as subclasses of unicode don't work


KEY = Qt.Key.Key_J
MODIFIER = Qt.KeyboardModifier.MetaModifier if ismacos else Qt.KeyboardModifier.ControlModifier


class SnipKey(NamedTuple):
    trigger: str
    syntaxes: frozenset[str]


def snip_key(trigger: str, *syntaxes: str) -> SnipKey:
    if '*' in syntaxes:
        return SnipKey(trigger, frozenset(all_text_syntaxes))
    return SnipKey(trigger, frozenset(syntaxes))


def contains(l1: int, r1: int, l2: int, r2: int) -> bool:
    # True iff (l2, r2) if contained in (l1, r1)
    return l2 > l1 and r2 < r1


builtin_snippets: dict[SnipKey, Snippet] = {  # {{{
    snip_key('Lorem', 'html', 'xml'): {
        'description': _('Insert filler text'),
        'template': '''\
<p>The actual teachings of the great explorer of the truth, the master-builder
of human happiness. No one rejects, dislikes, or avoids pleasure itself,
because it is pleasure, but because those who do not know how to pursue
pleasure rationally encounter consequences that are extremely painful.</p>

<p>Nor again is there anyone who loves or pursues or desires to obtain pain of
itself, because it is pain, but because occasionally circumstances occur in
which toil and pain can procure him some great pleasure. To take a trivial
example, which of us ever undertakes laborious physical exercise, except to
obtain some advantage from it? But.</p>
''',
    },
    snip_key('<<', 'html', 'xml'): {
        'description': _('Insert a tag'),
        'template': '<$1>${2*}</$1>$3',
    },
    snip_key('<>', 'html', 'xml'): {
        'description': _('Insert a self closing tag'),
        'template': '<$1/>$2',
    },
    snip_key('<a', 'html'): {
        'description': _('Insert a HTML link'),
        'template': '<a href="${1:filename}">${2*}</a>$3',
    },
    snip_key('<i', 'html'): {
        'description': _('Insert a HTML image'),
        'template': '<img src="${1:filename}" alt="${2*:description}" />$3',
    },
    snip_key('<c', 'html'): {
        'description': _('Insert a HTML tag with a class'),
        'template': '<$1 class="${2:classname}">${3*}</$1>$4',
    },
}  # }}}

# Parsing of snippets {{{
escape = unescape = None


def escape_funcs() -> tuple[Callable[[str], str], Callable[[str], str]]:
    global escape, unescape
    if escape is None or unescape is None:
        escapem = {('\\' + x): chr(i + 1) for i, x in enumerate('\\${}')}
        escape_pat = re.compile('|'.join(map(re.escape, escapem)))

        def escape(x: str) -> str:
            return escape_pat.sub(lambda m: escapem[m.group()], x.replace('\\\\', '\x01'))

        unescapem = {v: k[1] for k, v in escapem.items()}
        unescape_pat = re.compile('|'.join(unescapem))

        def unescape(x: str) -> str:
            return unescape_pat.sub(lambda m: unescapem[m.group()], x)

    return escape, unescape


class TabStop(str):
    num: int
    start: int
    is_toplevel: bool
    is_mirror: bool
    takes_selection: bool
    # Note that for tab stops nested in the default text of another tab stop,
    # __new__() sets this to the TabStop class rather than the parent instance
    parent: TabStop | type[TabStop] | None

    def __new__(self, raw: str, start_offset: int, tab_stops: list[TabStop], is_toplevel: bool = True) -> Self:  # ruff: ignore[bad-staticmethod-argument]
        if raw.endswith('}'):
            unescape = escape_funcs()[1]
            num, default = raw[2:-1].partition(':')[0::2]
            # Look for tab stops defined in the default text
            uraw, child_stops = parse_template(unescape(default), start_offset=start_offset, is_toplevel=False, grouped=False)
            for c in child_stops:
                c.parent = self
            tab_stops.extend(child_stops)
            self = str.__new__(self, uraw)
            if num.endswith('*'):
                self.takes_selection = True
                num = num[:-1]
            else:
                self.takes_selection = False
            self.num = int(num)
        else:
            self = str.__new__(self, '')
            self.num = int(raw[1:])
            self.takes_selection = False
        self.start = start_offset
        self.is_toplevel = is_toplevel
        self.is_mirror = False
        self.parent = None
        tab_stops.append(self)
        return self

    def __repr__(self) -> str:
        return (
            f'TabStop(text={str.__repr__(self)} num={self.num} start={self.start} is_mirror={self.is_mirror}'
            f' takes_selection={self.takes_selection} is_toplevel={self.is_toplevel})'
        )


@overload
def parse_template(
    template: str, start_offset: int = 0, is_toplevel: bool = True, grouped: Literal[True] = True
) -> tuple[str, dict[int, tuple[TabStop, ...]]]: ...
@overload
def parse_template(template: str, start_offset: int = 0, is_toplevel: bool = True, *, grouped: Literal[False]) -> tuple[str, list[TabStop]]: ...
def parse_template(
    template: str, start_offset: int = 0, is_toplevel: bool = True, grouped: bool = True
) -> tuple[str, dict[int, tuple[TabStop, ...]] | list[TabStop]]:
    escape, unescape = escape_funcs()
    template = escape(template)
    pos, parts, tab_stops = start_offset, [], []
    for part in re.split(r'(\$(?:\d+|\{[^}]+\}))', template):
        is_tab_stop = part.startswith('$')
        if is_tab_stop:
            ts = TabStop(part, pos, tab_stops, is_toplevel=is_toplevel)
            parts.append(ts)
        else:
            parts.append(unescape(part))
        pos += string_length(parts[-1])
    if grouped:
        key = attrgetter('num')
        tab_stops.sort(key=key)
        ans = OrderedDict()
        for num, stops in groupby(tab_stops, key):
            stops = tuple(stops)
            for ts in stops[1:]:
                ts.is_mirror = True
            ans[num] = stops
        tab_stops = ans
    return ''.join(parts), tab_stops


# }}}

_snippets: list[tuple[SnipKey, Snippet]] | None = None
user_snippets = JSONConfig('editor_snippets')


def snippets(refresh: bool = False) -> list[tuple[SnipKey, Snippet]]:
    global _snippets
    if _snippets is None or refresh:
        all_snippets = copy.deepcopy(builtin_snippets)
        for snip in user_snippets.get('snippets', []):
            if snip['trigger'] and isinstance(snip['trigger'], str):
                key = snip_key(snip['trigger'], *snip['syntaxes'])
                all_snippets[key] = {'template': snip['template'], 'description': snip['description']}
        _snippets = sorted(all_snippets.items(), key=(lambda key_snip: string_length(key_snip[0].trigger)), reverse=True)
    return _snippets


# Editor integration {{{


class EditorTabStop:
    def __init__(self, left: int, tab_stops: Sequence[TabStop], editor: PlainTextEdit) -> None:
        self.editor = weakref.ref(editor)
        tab_stop = tab_stops[0]
        self.num = tab_stop.num
        self.is_mirror = tab_stop.is_mirror
        self.is_deleted = False
        self.is_toplevel = tab_stop.is_toplevel
        self.takes_selection = tab_stop.takes_selection
        self.left = left + tab_stop.start
        l = string_length(tab_stop)
        self.right = self.left + l
        self.mirrors = tuple(EditorTabStop(left, [ts], editor) for ts in tab_stops[1:])
        self.ignore_position_update = False
        self.join_previous_edit = False
        self.transform: Callable[[str], str] | None = None
        self.has_transform = self.transform is not None

    def __enter__(self) -> None:
        self.join_previous_edit = True

    def __exit__(self, *args: object) -> None:
        self.join_previous_edit = False

    def __repr__(self) -> str:
        return (
            f'EditorTabStop(num={self.num!r} text={self.text!r} left={self.left!r} right={self.right!r} '
            f'is_deleted={self.is_deleted!r} mirrors={self.mirrors!r})'
        )

    __str__ = __unicode__ = __repr__

    def apply_selected_text(self, text: str) -> None:
        if self.takes_selection and not self.is_deleted:
            with self:
                self.text = text
            for m in self.mirrors:
                with m:
                    m.text = text

    @property
    def text(self) -> str:
        editor = self.editor()
        if editor is None or self.is_deleted:
            return ''
        c = editor.textCursor()
        c.setPosition(self.left), c.setPosition(self.right, QTextCursor.MoveMode.KeepAnchor)
        return editor.selected_text_from_cursor(c)

    @text.setter
    def text(self, text: str) -> None:
        editor = self.editor()
        if editor is None or self.is_deleted:
            return
        c = editor.textCursor()
        c.joinPreviousEditBlock() if self.join_previous_edit else c.beginEditBlock()
        c.setPosition(self.left), c.setPosition(self.right, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(text)
        c.endEditBlock()

    def set_editor_cursor(self, editor: PlainTextEdit) -> None:
        if not self.is_deleted:
            c = editor.textCursor()
            c.setPosition(self.left), c.setPosition(self.right, QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(c)

    def contained_in(self, left: int, right: int) -> bool:
        return contains(left, right, self.left, self.right)

    def contains(self, left: int, right: int) -> bool:
        return contains(self.left, self.right, left, right)

    def update_positions(self, position: int, chars_removed: int, chars_added: int) -> None:
        for m in self.mirrors:
            m.update_positions(position, chars_removed, chars_added)
        if position > self.right or self.is_deleted or self.ignore_position_update:
            return
        # First handle deletions
        if chars_removed > 0:
            if self.contained_in(position, position + chars_removed):
                self.is_deleted = True
                return
            if position <= self.left:
                self.left = max(self.left - chars_removed, position)
            if position <= self.right:
                self.right = max(self.right - chars_removed, position)

        if chars_added > 0:
            if position < self.left:
                self.left += chars_added
            if position <= self.right:
                self.right += chars_added


class Template(list):
    left_most_ts: EditorTabStop | None
    right_most_ts: EditorTabStop | None
    has_tab_stops: bool
    active_tab_stop: EditorTabStop | None

    def __new__(self, tab_stops: Iterable[EditorTabStop]) -> Self:  # ruff: ignore[bad-staticmethod-argument]
        self = list.__new__(self)
        self.left_most_ts = self.right_most_ts = None
        self.extend(tab_stops)
        for c in self:
            if self.left_most_ts is None or self.left_most_ts.left > c.left:
                self.left_most_ts = c
            if self.right_most_ts is None or self.right_most_ts.right <= c.right:
                self.right_most_ts = c
        self.has_tab_stops = bool(self)
        self.active_tab_stop = None
        return self

    @property
    def left_most_position(self) -> int | None:
        return getattr(self.left_most_ts, 'left', None)

    @property
    def right_most_position(self) -> int | None:
        return getattr(self.right_most_ts, 'right', None)

    def contains_cursor(self, cursor: QTextCursor) -> bool:
        if not self.has_tab_stops:
            return False
        pos = cursor.position()
        left, right = self.left_most_position, self.right_most_position
        # has_tab_stops guarantees that left and right are not None
        return left is not None and right is not None and left <= pos <= right

    def jump_to_next(self, editor: PlainTextEdit) -> EditorTabStop | None:
        if self.active_tab_stop is None:
            self.active_tab_stop = ts = self.find_closest_tab_stop(editor.textCursor().position())
            if ts is not None:
                ts.set_editor_cursor(editor)
            return ts
        ts = self.active_tab_stop
        if not ts.is_deleted:
            if ts.has_transform:
                assert ts.transform is not None
                ts.text = ts.transform(ts.text)
            for m in ts.mirrors:
                if not m.is_deleted:
                    m.text = ts.text
        for x in self:
            if x.num > ts.num and not x.is_deleted:
                self.active_tab_stop = x
                x.set_editor_cursor(editor)
                return x

    def remains_active(self) -> bool:
        if self.active_tab_stop is None:
            return False
        ts = self.active_tab_stop
        for x in self:
            if x.num > ts.num and not x.is_deleted:
                return True
        return bool(ts.mirrors) or ts.has_transform

    def find_closest_tab_stop(self, position: int) -> EditorTabStop | None:
        ans = dist = None
        for c in self:
            x = min(abs(c.left - position), abs(c.right - position))
            if ans is None or x < dist:
                dist, ans = x, c
        return ans


def expand_template(editor: PlainTextEdit, trigger: str, template: str) -> Template:
    c = editor.textCursor()
    c.beginEditBlock()
    c.setPosition(c.position())
    right = c.position()
    left = right - string_length(trigger)
    text, tab_stops = parse_template(template)
    c.setPosition(left), c.setPosition(right, QTextCursor.MoveMode.KeepAnchor), c.insertText(text)
    editor_tab_stops = [EditorTabStop(left, ts, editor) for ts in tab_stops.values()]

    tl = Template(editor_tab_stops)
    if tl.has_tab_stops:
        tl.active_tab_stop = ts = editor_tab_stops[0]
        ts.set_editor_cursor(editor)
    else:
        editor.setTextCursor(c)
    c.endEditBlock()
    return tl


def find_matching_snip(text: str, syntax: str | None = None, snip_func: SnippetsFunc | None = None) -> tuple[Snippet, str] | tuple[None, None]:
    for key, snip in (snip_func or snippets)():
        if text.endswith(key.trigger) and (syntax in key.syntaxes or syntax is None):
            return snip, key.trigger
    return None, None


class SnippetManager(QObject):
    def __init__(self, editor: PlainTextEdit) -> None:
        QObject.__init__(self, editor)
        self.active_templates: list[Template] = []
        self.last_selected_text = ''
        doc = editor.document()
        assert doc is not None
        doc.contentsChange.connect(self.contents_changed)
        self.snip_func: SnippetsFunc | None = None

    def contents_changed(self, position: int, chars_removed: int, chars_added: int) -> None:
        for template in self.active_templates:
            for ets in template:
                ets.update_positions(position, chars_removed, chars_added)

    def get_active_template(self, cursor: QTextCursor) -> Template | None:
        remove = []
        at = None
        pos = cursor.position()
        for template in self.active_templates:
            if at is None and template.contains_cursor(cursor):
                at = template
            else:
                left, right = template.left_most_position, template.right_most_position
                # active templates always have tab stops so left and right are never None
                if left is not None and right is not None and (pos > right or pos < left):
                    remove.append(template)
        for template in remove:
            self.active_templates.remove(template)
        return at

    def handle_key_press(self, ev: QKeyEvent) -> bool:
        editor_raw = self.parent()
        assert editor_raw is not None
        editor = cast('TextEdit', editor_raw)
        if ev.key() == KEY and ev.modifiers() & MODIFIER:
            at = self.get_active_template(editor.textCursor())
            if at is not None:
                if at.jump_to_next(editor) is None:
                    self.active_templates.remove(at)
                elif not at.remains_active():
                    self.active_templates.remove(at)
                ev.accept()
                return True
            lst, self.last_selected_text = self.last_selected_text, editor.selected_text
            if self.last_selected_text:
                editor.textCursor().insertText('')
                ev.accept()
                return True
            c, text = get_text_before_cursor(editor)
            snip, trigger = find_matching_snip(text, editor.syntax, self.snip_func)
            if snip is None or trigger is None:
                error_dialog(self.parent(), _('No snippet found'), _('No matching snippet was found'), show=True)
                self.last_selected_text = self.last_selected_text or lst
                return True
            template = expand_template(editor, trigger, snip['template'])
            if template.has_tab_stops:
                self.active_templates.append(template)
                if lst:
                    for ts in template:
                        ts.apply_selected_text(lst)

            ev.accept()
            return True
        return False


# }}}

# Config {{{


class SnippetTextEdit(PlainTextEdit):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        PlainTextEdit.__init__(self, parent)
        self.syntax = None
        if text:
            self.setPlainText(text)
        self.snippet_manager = SnippetManager(self)

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e is not None and self.snippet_manager.handle_key_press(e):
            return
        PlainTextEdit.keyPressEvent(self, e)


class EditSnippet(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)

        def add_row(*args: QWidget | str) -> None:
            r = l.rowCount()
            if len(args) == 1:
                w = args[0]
                assert isinstance(w, QWidget)
                l.addWidget(w, r, 0, 1, 2)
            else:
                text, w = args
                assert isinstance(text, str) and isinstance(w, QWidget)
                la = QLabel(text)
                l.addWidget(la, r, 0, Qt.AlignmentFlag.AlignRight), l.addWidget(w, r, 1)
                la.setBuddy(w)

        self.heading = la = QLabel('<h2>\xa0')
        add_row(la)
        self.helpl = la = QLabel(
            _('For help with snippets, see the <a href="%s">User Manual</a>') % localize_user_manual_link('https://manual.calibre-ebook.com/snippets.html')
        )
        la.setOpenExternalLinks(True)
        add_row(la)

        self.name = n = QLineEdit(self)
        n.setPlaceholderText(_('The name of this snippet'))
        add_row(_('&Name:'), n)

        self.trig = t = QLineEdit(self)
        t.setPlaceholderText(_('The text used to trigger this snippet'))
        add_row(_('Tri&gger:'), t)

        self.template = t = PlainTextEdit(self)
        la.setBuddy(t)
        add_row(_('&Template:'), t)

        self.types = t = QListWidget(self)
        t.setFlow(QListView.Flow.LeftToRight)
        t.setWrapping(True), t.setResizeMode(QListView.ResizeMode.Adjust), t.setSpacing(5)
        fm = t.fontMetrics()
        t.setMaximumHeight(2 * (fm.ascent() + fm.descent()) + 25)
        add_row(_('&File types:'), t)
        t.setToolTip(_('Which file types this snippet should be active in'))

        self.frame = f = QFrame(self)
        f.setFrameShape(QFrame.Shape.HLine)
        add_row(f)
        self.test = d = SnippetTextEdit('', self)
        d.snippet_manager.snip_func = self.snip_func
        d.setToolTip(_('You can test your snippet here'))
        d.setMaximumHeight(t.maximumHeight() + 15)
        add_row(_('T&est:'), d)

        i = QListWidgetItem(_('All'), t)
        i.setData(Qt.ItemDataRole.UserRole, '*')
        i.setCheckState(Qt.CheckState.Checked)
        i.setFlags(i.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        for ftype in sorted(all_text_syntaxes):
            i = QListWidgetItem(ftype, t)
            i.setData(Qt.ItemDataRole.UserRole, ftype)
            i.setCheckState(Qt.CheckState.Checked)
            i.setFlags(i.flags() | Qt.ItemFlag.ItemIsUserCheckable)

        self.creating_snippet = False

    def snip_func(self) -> tuple[tuple[SnipKey, Snippet]]:
        key = snip_key(self.trig.text(), '*')
        return ((key, self.snip),)

    def apply_snip(self, snip: Snippet | None, creating_snippet: bool | None = None) -> None:
        self.creating_snippet = not snip if creating_snippet is None else creating_snippet
        self.heading.setText('<h2>' + (_('Create a snippet') if self.creating_snippet else _('Edit snippet')))
        snip = snip or {}
        self.name.setText(snip.get('description') or '')
        self.trig.setText(snip.get('trigger') or '')
        self.template.setPlainText(snip.get('template') or '')

        ftypes = snip.get('syntaxes', ())
        for i in range(self.types.count()):
            i = self.types.item(i)
            assert i is not None
            ftype = i.data(Qt.ItemDataRole.UserRole)
            i.setCheckState(Qt.CheckState.Checked if ftype in ftypes else Qt.CheckState.Unchecked)
        if self.creating_snippet and not ftypes:
            _first_type_item = self.types.item(0)
            assert _first_type_item is not None
            _first_type_item.setCheckState(Qt.CheckState.Checked)
        (self.name if self.creating_snippet else self.template).setFocus(Qt.FocusReason.OtherFocusReason)

    @property
    def snip(self) -> Snippet:
        ftypes = []
        for i in range(self.types.count()):
            i = self.types.item(i)
            assert i is not None
            if i.checkState() == Qt.CheckState.Checked:
                ftypes.append(i.data(Qt.ItemDataRole.UserRole))
        return {
            'description': self.name.text().strip(),
            'trigger': self.trig.text(),
            'template': self.template.toPlainText(),
            'syntaxes': ftypes,
        }

    @snip.setter
    def snip(self, snip: Snippet | None) -> None:
        self.apply_snip(snip)

    def validate(self) -> str | None:
        snip = self.snip
        err = None
        if not snip['description']:
            err = _('You must provide a name for this snippet')
        elif not snip['trigger']:
            err = _('You must provide a trigger for this snippet')
        elif not snip['template']:
            err = _('You must provide a template for this snippet')
        elif not snip['syntaxes']:
            err = _('You must specify at least one file type')
        return err


class UserSnippets(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        Dialog.__init__(self, _('Create/edit snippets'), 'snippet-editor', parent=parent)
        self.setWindowIcon(QIcon.ic('snippets.png'))

    def setup_ui(self) -> None:
        self.setWindowIcon(QIcon.ic('modified.png'))
        self.l = l = QVBoxLayout(self)
        self.stack = s = QStackedLayout()
        l.addLayout(s), l.addWidget(self.bb)
        self.listc = c = QWidget(self)
        s.addWidget(c)
        l = QVBoxLayout(c)
        h = QHBoxLayout()
        l.addLayout(h)

        self.search_bar = sb = QLineEdit(self)
        sb.setPlaceholderText(_('Search for a snippet'))
        h.addWidget(sb)
        self.next_button = b = QPushButton(_('&Next'))
        b.clicked.connect(self.find_next)
        h.addWidget(b)

        h = QHBoxLayout()
        l.addLayout(h)
        self.snip_list = sl = QListWidget(self)
        sl.doubleClicked.connect(self.edit_snippet)
        h.addWidget(sl)

        l = QVBoxLayout()
        h.addLayout(l)
        self.add_button = b = QToolButton(self)
        (
            b.setIcon(QIcon.ic('plus.png')),
            b.setText(_('&Add snippet')),
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        )
        b.clicked.connect(self.add_snippet)
        l.addWidget(b)

        self.edit_button = b = QToolButton(self)
        (
            b.setIcon(QIcon.ic('modified.png')),
            b.setText(_('&Edit snippet')),
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        )
        b.clicked.connect(self.edit_snippet)
        l.addWidget(b)

        self.add_button = b = QToolButton(self)
        (
            b.setIcon(QIcon.ic('minus.png')),
            b.setText(_('&Remove snippet')),
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        )
        b.clicked.connect(self.remove_snippet)
        l.addWidget(b)

        self.add_button = b = QToolButton(self)
        (
            b.setIcon(QIcon.ic('config.png')),
            b.setText(_('Change &built-in')),
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon),
        )
        b.clicked.connect(self.change_builtin)
        l.addWidget(b)

        user_snips: list[Snippet] = user_snippets.get('snippets', [])
        for i, snip in enumerate(sorted(user_snips, key=itemgetter('trigger'))):
            item = self.snip_to_item(snip)
            if i == 0:
                self.snip_list.setCurrentItem(item)

        self.edit_snip = es = EditSnippet(self)
        self.stack.addWidget(es)

    def snip_to_text(self, snip: Snippet) -> str:
        return '{} - {}'.format(snip['trigger'], snip['description'])

    def snip_to_item(self, snip: Snippet) -> QListWidgetItem:
        i = QListWidgetItem(self.snip_to_text(snip), self.snip_list)
        i.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(snip))
        return i

    def reject(self) -> None:
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(0)
            return
        return Dialog.reject(self)

    def accept(self) -> None:
        if self.stack.currentIndex() > 0:
            err = self.edit_snip.validate()
            if err is None:
                self.stack.setCurrentIndex(0)
                if self.edit_snip.creating_snippet:
                    item = self.snip_to_item(self.edit_snip.snip)
                else:
                    item = self.snip_list.currentItem()
                    assert item is not None
                    snip = self.edit_snip.snip
                    item.setText(self.snip_to_text(snip))
                    item.setData(Qt.ItemDataRole.UserRole, snip)
                self.snip_list.setCurrentItem(item)
                self.snip_list.scrollToItem(item)
            else:
                error_dialog(self, _('Invalid snippet'), err, show=True)
            return
        _snippets_data = []
        for i in range(self.snip_list.count()):
            _snip_item = self.snip_list.item(i)
            assert _snip_item is not None
            _snippets_data.append(_snip_item.data(Qt.ItemDataRole.UserRole))
        user_snippets['snippets'] = _snippets_data
        snippets(refresh=True)
        return Dialog.accept(self)

    def sizeHint(self) -> QSize:
        return QSize(900, 600)

    def edit_snippet(self, *args: object) -> int | None:
        item = self.snip_list.currentItem()
        if item is None:
            return error_dialog(self, _('Cannot edit snippet'), _('No snippet selected'), show=True)
        self.stack.setCurrentIndex(1)
        self.edit_snip.snip = item.data(Qt.ItemDataRole.UserRole)

    def add_snippet(self, *args: object) -> None:
        self.stack.setCurrentIndex(1)
        self.edit_snip.snip = None

    def remove_snippet(self, *args: object) -> None:
        item = self.snip_list.currentItem()
        if item is not None:
            self.snip_list.takeItem(self.snip_list.row(item))

    def find_next(self, *args: object) -> int | None:
        q = self.search_bar.text().strip()
        if not q:
            return
        matches = self.snip_list.findItems(q, Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchWrap)
        if len(matches) < 1:
            return error_dialog(self, _('No snippets found'), _('No snippets found for query: %s') % q, show=True)
        ci = self.snip_list.currentItem()
        try:
            item = matches[(matches.index(ci) + 1) % len(matches)] if ci is not None else matches[0]
        except Exception:
            item = matches[0]
        self.snip_list.setCurrentItem(item)
        self.snip_list.scrollToItem(item)

    def change_builtin(self) -> None:
        d = QDialog(self)
        lw = QListWidget(d)
        for (trigger, syntaxes), snip in builtin_snippets.items():
            snip = copy.deepcopy(snip)
            snip['trigger'], snip['syntaxes'] = trigger, syntaxes
            i = QListWidgetItem(self.snip_to_text(snip), lw)
            i.setData(Qt.ItemDataRole.UserRole, snip)
        l = QVBoxLayout(d)
        l.addWidget(QLabel(_('Choose the built-in snippet to modify:')))
        l.addWidget(lw)
        lw.itemDoubleClicked.connect(d.accept)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
        if d.exec() == QDialog.DialogCode.Accepted and lw.currentItem() is not None:
            self.stack.setCurrentIndex(1)
            _lw_current_item = lw.currentItem()
            assert _lw_current_item is not None
            self.edit_snip.apply_snip(_lw_current_item.data(Qt.ItemDataRole.UserRole), creating_snippet=True)


# }}}

if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    d = UserSnippets()
    d.exec()
    del app
