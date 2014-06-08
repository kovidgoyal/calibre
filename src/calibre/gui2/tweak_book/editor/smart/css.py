#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.gui2.tweak_book.editor.smart import NullSmarts

def find_rule(raw, rule_address):
    import tinycss
    parser = tinycss.make_full_parser()
    sheet = parser.parse_stylesheet(raw)
    rules = sheet.rules
    ans = None, None
    while rule_address:
        try:
            r = rules[rule_address[0]]
        except IndexError:
            return None, None
        else:
            ans = r.line, r.column
        rule_address = rule_address[1:]
        if rule_address:
            rules = getattr(r, 'rules', ())
    return ans

class CSSSmarts(NullSmarts):
    pass

