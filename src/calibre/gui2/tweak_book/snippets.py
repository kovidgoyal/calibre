#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy
from collections import OrderedDict, namedtuple
from itertools import groupby
from operator import attrgetter

from PyQt5.Qt import QTextCursor, Qt, QObject

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book.editor import all_text_syntaxes
from calibre.gui2.tweak_book.editor.smarts.utils import get_text_before_cursor
from calibre.utils.config import JSONConfig
from calibre.utils.icu import string_length

SnipKey = namedtuple('SnipKey', 'trigger syntaxes')
def snip_key(trigger, *syntaxes):
    if '*' in syntaxes:
        syntaxes = all_text_syntaxes
    return SnipKey(trigger, frozenset(*syntaxes))

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
        'template': '<a href="$1">${2*}</a>',
    },

    snip_key('<i', 'html'): {
        'description': _('Insert a HTML image'),
        'template': '<img src="$1" alt="${2*}" />$3',
    },

    snip_key('<c', 'html'): {
        'description': _('Insert a HTML tag with a class'),
        'template': '<$1 class="$2">${3*}</$1>',
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

    def __init__(self, other, tab_stops):
        self.left = QTextCursor(other)
        self.right = QTextCursor(other)
        tab_stop = tab_stops[0]
        self.num = tab_stop.num
        self.is_mirror = tab_stop.is_mirror
        self.is_toplevel = tab_stop.is_toplevel
        self.takes_selection = tab_stop.takes_selection
        self.left.setPosition(other.anchor() + tab_stop.start)
        l = string_length(tab_stop)
        self.right.setPosition(self.left.position() + l)
        self.mirrors = tuple(EditorTabStop(other, [ts]) for ts in tab_stops[1:])

    def apply_selected_text(self, text):
        if self.takes_selection:
            self.text = text
            for m in self.mirrors:
                m.text = text

    @dynamic_property
    def text(self):
        def fget(self):
            from calibre.gui2.tweak_book.editor.text import selected_text_from_cursor
            c = QTextCursor(self.left)
            c.setPosition(self.right.position(), c.KeepAnchor)
            return selected_text_from_cursor(c)
        def fset(self, text):
            c = QTextCursor(self.left)
            c.setPosition(self.right.position(), c.KeepAnchor)
            c.insertText(text)
        return property(fget=fget, fset=fset)

    def set_editor_cursor(self, editor):
        c = editor.textCursor()
        c.setPosition(self.left.position())
        c.setPosition(self.right.position(), c.KeepAnchor)
        editor.setTextCursor(c)

class Template(list):

    def __new__(self, tab_stops):
        self = list.__new__(self, tab_stops)
        self.left_most_cursor = self.right_most_cursor = None
        for c in self:
            if self.left_most_cursor is None or self.left_most_cursor.position() > c.left.position():
                self.left_most_cursor = c.left
            if self.right_most_cursor is None or self.right_most_cursor.position() <= c.right.position():
                self.right_most_cursor = c.right
        self.has_tab_stops = self.left_most_cursor is not None
        self.active_tab_stop = None
        return self

    def contains_cursor(self, cursor):
        if not self.has_tab_stops:
            return False
        pos = cursor.position()
        if self.left_most_cursor.position() <= pos <= self.right_most_cursor.position():
            return True
        return False

    def jump_to_next(self, editor):
        if self.active_tab_stop is None:
            self.active_tab_stop = ts = self.find_closest_tab_stop(editor.textCursor().position())
            if ts is not None:
                ts.set_editor_cursor(editor)
            return ts
        ts = self.active_tab_stop
        for m in ts.mirrors:
            m.text = ts.text
        for x in self:
            if x.num > ts.num:
                self.active_tab_stop = x
                x.set_editor_cursor(editor)
                return x

    def distance_to_position(self, cursor, position):
        return min(abs(cursor.position() - position), abs(cursor.anchor() - position))

    def find_closest_tab_stop(self, position):
        ans = dist = None
        for c in self:
            x = min(self.distance_to_position(c.left, position), self.distance_to_position(c.right, position))
            if ans is None or x < dist:
                dist, ans = x, c
        return ans

def expand_template(editor, trigger, template, selected_text=''):
    c = editor.textCursor()
    c.setPosition(c.position())
    right = c.position()
    left = right - string_length(trigger)
    text, tab_stops = parse_template(template)
    c.setPosition(left), c.setPosition(right, c.KeepAnchor), c.insertText(text)
    editor_tab_stops = [EditorTabStop(c, ts) for ts in tab_stops]

    if selected_text:
        for ts in editor_tab_stops:
            ts.apply_selected_text(selected_text)
    tl = Template(editor_tab_stops)
    if tl.has_tab_stops:
        tl.active_tab_stop = ts = editor_tab_stops[0]
        ts.set_editor_cursor(editor)
    else:
        editor.setTextCursor(c)
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

    def get_active_template(self, cursor):
        remove = []
        at = None
        pos = cursor.position()
        for template in self.active_templates:
            if at is None and template.contains_cursor(cursor):
                at = template
            elif pos > template.right_most_cursor.position() or pos < template.left_most_cursor.position():
                remove.append(template)
        for template in remove:
            self.active_templates.remove(template)
        return at

    def handle_keypress(self, ev):
        editor = self.parent()
        if ev.key() == Qt.Key_Tab and ev.modifiers() & Qt.CTRL:
            at = self.get_active_template(editor.cursor())
            if at is not None:
                if at.jump_to_next(editor) is None:
                    self.active_templates.remove(at)
                ev.accept()
                return True
            self.last_selected_text = editor.selected_text
            if self.last_selected_text:
                editor.textCursor().insertText('')
                ev.accept()
                return True
            c, text = get_text_before_cursor(editor)
            snip, trigger = find_matching_snip(text, editor.syntax)
            if snip is None:
                error_dialog(self.parent(), _('No snippet found'), _(
                    'No matching snippet was found'), show=True)
                return False
            template = expand_template(editor, trigger, snip['template'], self.last_selected_text)
            if template.has_tab_stops:
                self.active_templates.append(template)
            ev.accept()
            return True
        return False
