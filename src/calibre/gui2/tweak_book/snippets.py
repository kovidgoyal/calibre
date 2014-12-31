#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, copy
from collections import OrderedDict
from itertools import groupby
from operator import attrgetter

from PyQt5.Qt import QTextCursor

from calibre.utils.config import JSONConfig
from calibre.utils.icu import string_length

builtin_snippets = {  # {{{
    '<<' : {
        'description': _('Insert a HTML tag'),
        'template': '<$1>${2*}</$1>',
    },

    '<>' : {
        'description': _('Insert a self closing HTML tag'),
        'template': '<$1/>$2',
    },

    '<a' : {
        'description': _('Insert a HTML link'),
        'template': '<a href="$1">${2*}</a>',
    },

    '<i' : {
        'description': _('Insert a HTML image'),
        'template': '<img src="$1" alt="${2*}" />$3',
    },

    '<c' : {
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

def snippets():
    global _snippets
    if _snippets is None:
        _snippets = copy.deepcopy(builtin_snippets)
        us = copy.deepcopy(user_snippets.copy())
        _snippets.update(us)
    return _snippets

class TabStopCursor(QTextCursor):

    def __init__(self, other, tab_stops):
        QTextCursor.__init__(self, other)
        tab_stop = tab_stops[0]
        self.num = tab_stop.num
        self.is_mirror = tab_stop.is_mirror
        self.is_toplevel = tab_stop.is_toplevel
        self.takes_selection = tab_stop.takes_selection
        self.visited = False
        self.setPosition(other.anchor() + tab_stop.start)
        l = string_length(tab_stop)
        if l > 0:
            self.setPosition(self.position() + l, self.KeepAnchor)
        self.mirrors = []
        for ts in tab_stops[1:]:
            m = QTextCursor(other)
            m.setPosition(other.anchor() + ts.start)
            l = string_length(ts)
            if l > 0:
                m.setPosition(m.position() + l, m.KeepAnchor)
            self.mirrors.append(m)

class CursorCollection(list):

    def __new__(self, cursors):
        self = list.__new__(self, cursors)
        self.left_most_cursor = self.right_most_cursor = None
        for c in self:
            if self.left_most_cursor is None or self.left_most_cursor.anchor() > c.anchor():
                self.left_most_cursor = c
            if self.right_most_cursor is None or self.right_most_cursor.position() <= c.position():
                self.right_most_cursor = c
        return self

def expand_template(editor, template_name, template, selected_text=''):
    c = editor.textCursor()
    c.setPosition(c.position())
    right = c.position()
    left = right - string_length(template_name)
    text, tab_stops = parse_template(template)
    cursors = []
    c.setPosition(left), c.setPosition(right, c.KeepAnchor), c.insertText(text)
    for i, ts in enumerate(tab_stops.itervalues()):
        tsc = TabStopCursor(c, ts)
        cursors.append(tsc)

    if selected_text:
        for tsc in cursors:
            pos = min(tsc.anchor(), tsc.position())
            tsc.insertText(selected_text)
            apos = tsc.position()
            tsc.setPosition(pos), tsc.setPosition(apos, tsc.KeepAnchor)
    active_cursor = (cursors or [c])[0]
    active_cursor.visited = True
    editor.setTextCursor(active_cursor)
    return CursorCollection(cursors)
