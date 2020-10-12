#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy, weakref
from collections import OrderedDict, namedtuple
from itertools import groupby
from operator import attrgetter, itemgetter

from PyQt5.Qt import (
    Qt, QObject, QSize, QVBoxLayout, QStackedLayout, QWidget, QLineEdit,
    QToolButton, QIcon, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QGridLayout, QPlainTextEdit, QLabel, QFrame, QDialog, QDialogButtonBox)

from calibre.constants import ismacos
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor import all_text_syntaxes
from calibre.gui2.tweak_book.editor.smarts.utils import get_text_before_cursor
from calibre.gui2.tweak_book.widgets import Dialog, PlainTextEdit
from calibre.utils.config import JSONConfig
from calibre.utils.icu import string_length as strlen
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import codepoint_to_chr, iteritems, itervalues, unicode_type, range

string_length = lambda x: strlen(unicode_type(x))  # Needed on narrow python builds, as subclasses of unicode dont work
KEY = Qt.Key_J
MODIFIER = Qt.META if ismacos else Qt.CTRL

SnipKey = namedtuple('SnipKey', 'trigger syntaxes')


def snip_key(trigger, *syntaxes):
    if '*' in syntaxes:
        syntaxes = all_text_syntaxes
    return SnipKey(trigger, frozenset(syntaxes))


def contains(l1, r1, l2, r2):
    # True iff (l2, r2) if contained in (l1, r1)
    return l2 > l1 and r2 < r1


builtin_snippets = {  # {{{
    snip_key('Lorem', 'html', 'xml'):  {
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

    snip_key('<<', 'html', 'xml'):  {
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


def escape_funcs():
    global escape, unescape
    if escape is None:
        escapem = {('\\' + x):codepoint_to_chr(i+1) for i, x in enumerate('\\${}')}
        escape_pat = re.compile('|'.join(map(re.escape, escapem)))
        escape = lambda x: escape_pat.sub(lambda m: escapem[m.group()], x.replace(r'\\', '\x01'))
        unescapem = {v:k[1] for k, v in iteritems(escapem)}
        unescape_pat = re.compile('|'.join(unescapem))
        unescape = lambda x:unescape_pat.sub(lambda m:unescapem[m.group()], x)
    return escape, unescape


class TabStop(unicode_type):

    def __new__(self, raw, start_offset, tab_stops, is_toplevel=True):
        if raw.endswith('}'):
            unescape = escape_funcs()[1]
            num, default = raw[2:-1].partition(':')[0::2]
            # Look for tab stops defined in the default text
            uraw, child_stops = parse_template(unescape(default), start_offset=start_offset, is_toplevel=False, grouped=False)
            for c in child_stops:
                c.parent = self
            tab_stops.extend(child_stops)
            self = unicode_type.__new__(self, uraw)
            if num.endswith('*'):
                self.takes_selection = True
                num = num[:-1]
            else:
                self.takes_selection = False
            self.num = int(num)
        else:
            self = unicode_type.__new__(self, '')
            self.num = int(raw[1:])
            self.takes_selection = False
        self.start = start_offset
        self.is_toplevel = is_toplevel
        self.is_mirror = False
        self.parent = None
        tab_stops.append(self)
        return self

    def __repr__(self):
        return 'TabStop(text=%s num=%d start=%d is_mirror=%s takes_selection=%s is_toplevel=%s)' % (
            unicode_type.__repr__(self), self.num, self.start, self.is_mirror, self.takes_selection, self.is_toplevel)


def parse_template(template, start_offset=0, is_toplevel=True, grouped=True):
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


_snippets = None
user_snippets = JSONConfig('editor_snippets')


def snippets(refresh=False):
    global _snippets
    if _snippets is None or refresh:
        _snippets = copy.deepcopy(builtin_snippets)
        for snip in user_snippets.get('snippets', []):
            if snip['trigger'] and isinstance(snip['trigger'], unicode_type):
                key = snip_key(snip['trigger'], *snip['syntaxes'])
                _snippets[key] = {'template':snip['template'], 'description':snip['description']}
        _snippets = sorted(iteritems(_snippets), key=(lambda key_snip:string_length(key_snip[0].trigger)), reverse=True)
    return _snippets

# Editor integration {{{


class EditorTabStop(object):

    def __init__(self, left, tab_stops, editor):
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
        self.transform = None
        self.has_transform = self.transform is not None

    def __enter__(self):
        self.join_previous_edit = True

    def __exit__(self, *args):
        self.join_previous_edit = False

    def __repr__(self):
        return 'EditorTabStop(num=%r text=%r left=%r right=%r is_deleted=%r mirrors=%r)' % (
            self.num, self.text, self.left, self.right, self.is_deleted, self.mirrors)
    __str__ = __unicode__ = __repr__

    def apply_selected_text(self, text):
        if self.takes_selection and not self.is_deleted:
            with self:
                self.text = text
            for m in self.mirrors:
                with m:
                    m.text = text

    @property
    def text(self):
        editor = self.editor()
        if editor is None or self.is_deleted:
            return ''
        c = editor.textCursor()
        c.setPosition(self.left), c.setPosition(self.right, c.KeepAnchor)
        return editor.selected_text_from_cursor(c)

    @text.setter
    def text(self, text):
        editor = self.editor()
        if editor is None or self.is_deleted:
            return
        c = editor.textCursor()
        c.joinPreviousEditBlock() if self.join_previous_edit else c.beginEditBlock()
        c.setPosition(self.left), c.setPosition(self.right, c.KeepAnchor)
        c.insertText(text)
        c.endEditBlock()

    def set_editor_cursor(self, editor):
        if not self.is_deleted:
            c = editor.textCursor()
            c.setPosition(self.left), c.setPosition(self.right, c.KeepAnchor)
            editor.setTextCursor(c)

    def contained_in(self, left, right):
        return contains(left, right, self.left, self.right)

    def contains(self, left, right):
        return contains(self.left, self.right, left, right)

    def update_positions(self, position, chars_removed, chars_added):
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

    def __new__(self, tab_stops):
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
    def left_most_position(self):
        return getattr(self.left_most_ts, 'left', None)

    @property
    def right_most_position(self):
        return getattr(self.right_most_ts, 'right', None)

    def contains_cursor(self, cursor):
        if not self.has_tab_stops:
            return False
        pos = cursor.position()
        if self.left_most_position <= pos <= self.right_most_position:
            return True
        return False

    def jump_to_next(self, editor):
        if self.active_tab_stop is None:
            self.active_tab_stop = ts = self.find_closest_tab_stop(editor.textCursor().position())
            if ts is not None:
                ts.set_editor_cursor(editor)
            return ts
        ts = self.active_tab_stop
        if not ts.is_deleted:
            if ts.has_transform:
                ts.text = ts.transform(ts.text)
            for m in ts.mirrors:
                if not m.is_deleted:
                    m.text = ts.text
        for x in self:
            if x.num > ts.num and not x.is_deleted:
                self.active_tab_stop = x
                x.set_editor_cursor(editor)
                return x

    def remains_active(self):
        if self.active_tab_stop is None:
            return False
        ts = self.active_tab_stop
        for x in self:
            if x.num > ts.num and not x.is_deleted:
                return True
        return bool(ts.mirrors) or ts.has_transform

    def find_closest_tab_stop(self, position):
        ans = dist = None
        for c in self:
            x = min(abs(c.left - position), abs(c.right - position))
            if ans is None or x < dist:
                dist, ans = x, c
        return ans


def expand_template(editor, trigger, template):
    c = editor.textCursor()
    c.beginEditBlock()
    c.setPosition(c.position())
    right = c.position()
    left = right - string_length(trigger)
    text, tab_stops = parse_template(template)
    c.setPosition(left), c.setPosition(right, c.KeepAnchor), c.insertText(text)
    editor_tab_stops = [EditorTabStop(left, ts, editor) for ts in itervalues(tab_stops)]

    tl = Template(editor_tab_stops)
    if tl.has_tab_stops:
        tl.active_tab_stop = ts = editor_tab_stops[0]
        ts.set_editor_cursor(editor)
    else:
        editor.setTextCursor(c)
    c.endEditBlock()
    return tl


def find_matching_snip(text, syntax=None, snip_func=None):
    ans_snip = ans_trigger = None
    for key, snip in (snip_func or snippets)():
        if text.endswith(key.trigger) and (syntax in key.syntaxes or syntax is None):
            ans_snip, ans_trigger = snip, key.trigger
            break
    return ans_snip, ans_trigger


class SnippetManager(QObject):

    def __init__(self, editor):
        QObject.__init__(self, editor)
        self.active_templates = []
        self.last_selected_text = ''
        editor.document().contentsChange.connect(self.contents_changed)
        self.snip_func = None

    def contents_changed(self, position, chars_removed, chars_added):
        for template in self.active_templates:
            for ets in template:
                ets.update_positions(position, chars_removed, chars_added)

    def get_active_template(self, cursor):
        remove = []
        at = None
        pos = cursor.position()
        for template in self.active_templates:
            if at is None and template.contains_cursor(cursor):
                at = template
            elif pos > template.right_most_position or pos < template.left_most_position:
                remove.append(template)
        for template in remove:
            self.active_templates.remove(template)
        return at

    def handle_key_press(self, ev):
        editor = self.parent()
        if ev.key() == KEY and ev.modifiers() & MODIFIER:
            at = self.get_active_template(editor.textCursor())
            if at is not None:
                if at.jump_to_next(editor) is None:
                    self.active_templates.remove(at)
                else:
                    if not at.remains_active():
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
            if snip is None:
                error_dialog(self.parent(), _('No snippet found'), _(
                    'No matching snippet was found'), show=True)
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

    def __init__(self, text, parent=None):
        PlainTextEdit.__init__(self, parent)
        if text:
            self.setPlainText(text)
        self.snippet_manager = SnippetManager(self)

    def keyPressEvent(self, ev):
        if self.snippet_manager.handle_key_press(ev):
            return
        PlainTextEdit.keyPressEvent(self, ev)


class EditSnippet(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)

        def add_row(*args):
            r = l.rowCount()
            if len(args) == 1:
                l.addWidget(args[0], r, 0, 1, 2)
            else:
                la = QLabel(args[0])
                l.addWidget(la, r, 0, Qt.AlignRight), l.addWidget(args[1], r, 1)
                la.setBuddy(args[1])

        self.heading = la = QLabel('<h2>\xa0')
        add_row(la)
        self.helpl = la = QLabel(_('For help with snippets, see the <a href="%s">User Manual</a>') %
                                 localize_user_manual_link('https://manual.calibre-ebook.com/snippets.html'))
        la.setOpenExternalLinks(True)
        add_row(la)

        self.name = n = QLineEdit(self)
        n.setPlaceholderText(_('The name of this snippet'))
        add_row(_('&Name:'), n)

        self.trig = t = QLineEdit(self)
        t.setPlaceholderText(_('The text used to trigger this snippet'))
        add_row(_('Tri&gger:'), t)

        self.template = t = QPlainTextEdit(self)
        la.setBuddy(t)
        add_row(_('&Template:'), t)

        self.types = t = QListWidget(self)
        t.setFlow(t.LeftToRight)
        t.setWrapping(True), t.setResizeMode(t.Adjust), t.setSpacing(5)
        fm = t.fontMetrics()
        t.setMaximumHeight(2*(fm.ascent() + fm.descent()) + 25)
        add_row(_('&File types:'), t)
        t.setToolTip(_('Which file types this snippet should be active in'))

        self.frame = f = QFrame(self)
        f.setFrameShape(f.HLine)
        add_row(f)
        self.test = d = SnippetTextEdit('', self)
        d.snippet_manager.snip_func = self.snip_func
        d.setToolTip(_('You can test your snippet here'))
        d.setMaximumHeight(t.maximumHeight() + 15)
        add_row(_('T&est:'), d)

        i = QListWidgetItem(_('All'), t)
        i.setData(Qt.UserRole, '*')
        i.setCheckState(Qt.Checked)
        i.setFlags(i.flags() | Qt.ItemIsUserCheckable)
        for ftype in sorted(all_text_syntaxes):
            i = QListWidgetItem(ftype, t)
            i.setData(Qt.UserRole, ftype)
            i.setCheckState(Qt.Checked)
            i.setFlags(i.flags() | Qt.ItemIsUserCheckable)

        self.creating_snippet = False

    def snip_func(self):
        key = snip_key(self.trig.text(), '*')
        return ((key, self.snip),)

    def apply_snip(self, snip, creating_snippet=None):
        self.creating_snippet = not snip if creating_snippet is None else creating_snippet
        self.heading.setText('<h2>' + (_('Create a snippet') if self.creating_snippet else _('Edit snippet')))
        snip = snip or {}
        self.name.setText(snip.get('description') or '')
        self.trig.setText(snip.get('trigger') or '')
        self.template.setPlainText(snip.get('template') or '')

        ftypes = snip.get('syntaxes', ())
        for i in range(self.types.count()):
            i = self.types.item(i)
            ftype = i.data(Qt.UserRole)
            i.setCheckState(Qt.Checked if ftype in ftypes else Qt.Unchecked)
        if self.creating_snippet and not ftypes:
            self.types.item(0).setCheckState(Qt.Checked)
        (self.name if self.creating_snippet else self.template).setFocus(Qt.OtherFocusReason)

    @property
    def snip(self):
        ftypes = []
        for i in range(self.types.count()):
            i = self.types.item(i)
            if i.checkState() == Qt.Checked:
                ftypes.append(i.data(Qt.UserRole))
        return {'description':self.name.text().strip(), 'trigger':self.trig.text(), 'template':self.template.toPlainText(), 'syntaxes':ftypes}

    @snip.setter
    def snip(self, snip):
        self.apply_snip(snip)

    def validate(self):
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

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Create/edit snippets'), 'snippet-editor', parent=parent)
        self.setWindowIcon(QIcon(I('snippets.png')))

    def setup_ui(self):
        self.setWindowIcon(QIcon(I('modified.png')))
        self.l = l = QVBoxLayout(self)
        self.stack = s = QStackedLayout()
        l.addLayout(s), l.addWidget(self.bb)
        self.listc = c = QWidget(self)
        s.addWidget(c)
        c.l = l = QVBoxLayout(c)
        c.h = h = QHBoxLayout()
        l.addLayout(h)

        self.search_bar = sb = QLineEdit(self)
        sb.setPlaceholderText(_('Search for a snippet'))
        h.addWidget(sb)
        self.next_button = b = QPushButton(_('&Next'))
        b.clicked.connect(self.find_next)
        h.addWidget(b)

        c.h2 = h = QHBoxLayout()
        l.addLayout(h)
        self.snip_list = sl = QListWidget(self)
        sl.doubleClicked.connect(self.edit_snippet)
        h.addWidget(sl)

        c.l2 = l = QVBoxLayout()
        h.addLayout(l)
        self.add_button = b = QToolButton(self)
        b.setIcon(QIcon(I('plus.png'))), b.setText(_('&Add snippet')), b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.clicked.connect(self.add_snippet)
        l.addWidget(b)

        self.edit_button = b = QToolButton(self)
        b.setIcon(QIcon(I('modified.png'))), b.setText(_('&Edit snippet')), b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.clicked.connect(self.edit_snippet)
        l.addWidget(b)

        self.add_button = b = QToolButton(self)
        b.setIcon(QIcon(I('minus.png'))), b.setText(_('&Remove snippet')), b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.clicked.connect(self.remove_snippet)
        l.addWidget(b)

        self.add_button = b = QToolButton(self)
        b.setIcon(QIcon(I('config.png'))), b.setText(_('Change &built-in')), b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.clicked.connect(self.change_builtin)
        l.addWidget(b)

        for i, snip in enumerate(sorted(user_snippets.get('snippets', []), key=itemgetter('trigger'))):
            item = self.snip_to_item(snip)
            if i == 0:
                self.snip_list.setCurrentItem(item)

        self.edit_snip = es = EditSnippet(self)
        self.stack.addWidget(es)

    def snip_to_text(self, snip):
        return '%s - %s' % (snip['trigger'], snip['description'])

    def snip_to_item(self, snip):
        i = QListWidgetItem(self.snip_to_text(snip), self.snip_list)
        i.setData(Qt.UserRole, copy.deepcopy(snip))
        return i

    def reject(self):
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(0)
            return
        return Dialog.reject(self)

    def accept(self):
        if self.stack.currentIndex() > 0:
            err = self.edit_snip.validate()
            if err is None:
                self.stack.setCurrentIndex(0)
                if self.edit_snip.creating_snippet:
                    item = self.snip_to_item(self.edit_snip.snip)
                else:
                    item = self.snip_list.currentItem()
                    snip = self.edit_snip.snip
                    item.setText(self.snip_to_text(snip))
                    item.setData(Qt.UserRole, snip)
                self.snip_list.setCurrentItem(item)
                self.snip_list.scrollToItem(item)
            else:
                error_dialog(self, _('Invalid snippet'), err, show=True)
            return
        user_snippets['snippets'] = [self.snip_list.item(i).data(Qt.UserRole) for i in range(self.snip_list.count())]
        snippets(refresh=True)
        return Dialog.accept(self)

    def sizeHint(self):
        return QSize(900, 600)

    def edit_snippet(self, *args):
        item = self.snip_list.currentItem()
        if item is None:
            return error_dialog(self, _('Cannot edit snippet'), _('No snippet selected'), show=True)
        self.stack.setCurrentIndex(1)
        self.edit_snip.snip = item.data(Qt.UserRole)

    def add_snippet(self, *args):
        self.stack.setCurrentIndex(1)
        self.edit_snip.snip = None

    def remove_snippet(self, *args):
        item = self.snip_list.currentItem()
        if item is not None:
            self.snip_list.takeItem(self.snip_list.row(item))

    def find_next(self, *args):
        q = self.search_bar.text().strip()
        if not q:
            return
        matches = self.snip_list.findItems(q, Qt.MatchContains | Qt.MatchWrap)
        if len(matches) < 1:
            return error_dialog(self, _('No snippets found'), _(
                'No snippets found for query: %s') % q, show=True)
        ci = self.snip_list.currentItem()
        try:
            item = matches[(matches.index(ci) + 1) % len(matches)]
        except Exception:
            item = matches[0]
        self.snip_list.setCurrentItem(item)
        self.snip_list.scrollToItem(item)

    def change_builtin(self):
        d = QDialog(self)
        lw = QListWidget(d)
        for (trigger, syntaxes), snip in iteritems(builtin_snippets):
            snip = copy.deepcopy(snip)
            snip['trigger'], snip['syntaxes'] = trigger, syntaxes
            i = QListWidgetItem(self.snip_to_text(snip), lw)
            i.setData(Qt.UserRole, snip)
        d.l = l = QVBoxLayout(d)
        l.addWidget(QLabel(_('Choose the built-in snippet to modify:')))
        l.addWidget(lw)
        lw.itemDoubleClicked.connect(d.accept)
        d.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
        if d.exec_() == d.Accepted and lw.currentItem() is not None:
            self.stack.setCurrentIndex(1)
            self.edit_snip.apply_snip(lw.currentItem().data(Qt.UserRole), creating_snippet=True)
# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    d = UserSnippets()
    d.exec_()
    del app
