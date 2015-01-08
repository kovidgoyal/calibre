#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy, weakref
from collections import OrderedDict, namedtuple
from itertools import groupby
from operator import attrgetter

from PyQt5.Qt import Qt, QObject

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor import all_text_syntaxes
from calibre.gui2.tweak_book.editor.smarts.utils import get_text_before_cursor
from calibre.utils.config import JSONConfig
from calibre.utils.icu import string_length

SnipKey = namedtuple('SnipKey', 'trigger syntaxes')
def snip_key(trigger, *syntaxes):
    if '*' in syntaxes:
        syntaxes = all_text_syntaxes
    return SnipKey(trigger, frozenset(syntaxes))

def contains(l1, r1, l2, r2):
    # True iff (l2, r2) if contained in (l1, r1)
    return l2 >= l1 and r2 <= r1

builtin_snippets = {  # {{{
    snip_key('<<', 'html', 'xml'):  {
        'description': _('Insert a tag'),
        'template': '<$1>${2*}</$1>',
    },

    snip_key('<>', 'html', 'xml'): {
        'description': _('Insert a self closing tag'),
        'template': '<$1/>$2',
    },

    snip_key('<a', 'html'): {
        'description': _('Insert a HTML link'),
        'template': '<a href="${1:filename}">${2*}</a>',
    },

    snip_key('<i', 'html'): {
        'description': _('Insert a HTML image'),
        'template': '<img src="${1:filename}" alt="${2*:description}" />$3',
    },

    snip_key('<c', 'html'): {
        'description': _('Insert a HTML tag with a class'),
        'template': '<$1 class="${2:classname}">${3*}</$1>',
    },

}  # }}}

# Parsing of snippets {{{
escape = unescape = None
def escape_funcs():
    global escape, unescape
    if escape is None:
        escapem = {('\\' + x):unichr(i+1) for i, x in enumerate('\\${}')}
        escape_pat = re.compile('|'.join(map(re.escape, escapem)))
        escape = lambda x: escape_pat.sub(lambda m: escapem[m.group()], x.replace(r'\\', '\x01'))
        unescapem = {v:k[1] for k, v in escapem.iteritems()}
        unescape_pat = re.compile('|'.join(unescapem))
        unescape = lambda x:unescape_pat.sub(lambda m:unescapem[m.group()], x)
    return escape, unescape

class TabStop(unicode):

    def __new__(self, raw, start_offset, tab_stops, is_toplevel=True):
        if raw.endswith('}'):
            unescape = escape_funcs()[1]
            num, default = raw[2:-1].partition(':')[0::2]
            # Look for tab stops defined in the default text
            uraw, child_stops = parse_template(unescape(default), start_offset=start_offset, is_toplevel=False, grouped=False)
            for c in child_stops:
                c.parent = self
            tab_stops.extend(child_stops)
            self = unicode.__new__(self, uraw)
            if num.endswith('*'):
                self.takes_selection = True
                num = num[:-1]
            else:
                self.takes_selection = False
            self.num = int(num)
        else:
            self = unicode.__new__(self, '')
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
            unicode.__repr__(self), self.num, self.start, self.is_mirror, self.takes_selection, self.is_toplevel)
    __str__ = __unicode__ = __repr__

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
            if snip['trigger'] and isinstance(snip['trigger'], type('')):
                key = snip_key(snip['trigger'], *snip['syntaxes'])
                _snippets[key] = {'template':snip['template'], 'description':snip['description']}
    return _snippets

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

    @dynamic_property
    def text(self):
        def fget(self):
            editor = self.editor()
            if editor is None or self.is_deleted:
                return ''
            c = editor.textCursor()
            c.setPosition(self.left), c.setPosition(self.right, c.KeepAnchor)
            return editor.selected_text_from_cursor(c)
        def fset(self, text):
            editor = self.editor()
            if editor is None or self.is_deleted:
                return
            c = editor.textCursor()
            c.joinPreviousEditBlock() if self.join_previous_edit else c.beginEditBlock()
            c.setPosition(self.left), c.setPosition(self.right, c.KeepAnchor)
            c.insertText(text)
            c.endEditBlock()
        return property(fget=fget, fset=fset)

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
                self.left -= chars_removed
            if position <= self.right:
                self.right -= chars_removed

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
    editor_tab_stops = [EditorTabStop(left, ts, editor) for ts in tab_stops.itervalues()]

    tl = Template(editor_tab_stops)
    if tl.has_tab_stops:
        tl.active_tab_stop = ts = editor_tab_stops[0]
        ts.set_editor_cursor(editor)
    else:
        editor.setTextCursor(c)
    c.endEditBlock()
    return tl

def find_matching_snip(text, syntax):
    for key, snip in snippets().iteritems():
        if text.endswith(key.trigger) and syntax in key.syntaxes:
            return snip, key.trigger
    return None, None

class SnippetManager(QObject):

    def __init__(self, editor):
        QObject.__init__(self, editor)
        self.active_templates = []
        self.last_selected_text = ''
        editor.document().contentsChange.connect(self.contents_changed)

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
        if ev.key() == Qt.Key_Tab and ev.modifiers() & Qt.CTRL:
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
            snip, trigger = find_matching_snip(text, editor.syntax)
            if snip is None:
                error_dialog(self.parent(), _('No snippet found'), _(
                    'No matching snippet was found'), show=True)
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
