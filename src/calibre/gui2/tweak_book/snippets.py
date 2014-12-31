#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import OrderedDict
from itertools import groupby
from operator import attrgetter

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
        return 'TabStop(text=%s, num=%d, start=%d, is_mirror=%s takes_selection=%s is_toplevel=%s)' % (
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
