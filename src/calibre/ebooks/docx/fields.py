#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from calibre.ebooks.docx.names import XPath, get

class Field(object):

    def __init__(self, start):
        self.start = start
        self.end = None
        self.contents = []
        self.instructions = []

    def add_instr(self, elem):
        raw = elem.text
        if not raw:
            return
        name, rest = raw.strip().partition(' ')[0::2]
        self.instructions.append((name, rest.strip()))

WORD, FLAG = 0, 1
scanner = re.Scanner([
    (r'\\\S{1}', lambda s, t: (t, FLAG)),  # A flag of the form \x
    (r'"[^"]*"', lambda s, t: (t[1:-1], WORD)),  # Quoted word
    (r'[^\s\\"]\S*', lambda s, t: (t, WORD)),  # A non-quoted word, must not start with a backslash or a space or a quote
    (r'\s+', None),
], flags=re.DOTALL)


def parse_hyperlink(raw, log):
    ans = {}
    last_option = None
    for token, token_type in scanner.scan(raw)[0]:
        if not ans:
            if token_type is not WORD:
                log('Invalid hyperlink, first token is not a URL (%s)' % raw)
                return ans
            ans['url'] = token
        if token_type is FLAG:
            last_option = {'l':'anchor', 'm':'image-map', 'n':'target', 'o':'title', 't':'target'}.get(token[1], None)
            if last_option is not None:
                ans[last_option] = None
        elif token_type is WORD:
            if last_option is not None:
                ans[last_option] = token
    return ans


class Fields(object):

    def __init__(self):
        self.fields = []

    def __call__(self, doc, log):
        stack = []
        for elem in XPath(
            '//*[name()="w:p" or name()="w:r" or name()="w:instrText" or (name()="w:fldChar" and (@w:fldCharType="begin" or @w:fldCharType="end"))]')(doc):
            if elem.tag.endswith('}fldChar'):
                typ = get(elem, 'w:fldCharType')
                if typ == 'begin':
                    stack.append(Field(elem))
                    self.fields.append(stack[-1])
                else:
                    try:
                        stack.pop().end = elem
                    except IndexError:
                        pass
            elif elem.tag.endswith('}instrText'):
                if stack:
                    stack[-1].add_instr(elem)
            else:
                if stack:
                    stack[-1].contents.append(elem)

        # Parse hyperlink fields
        self.hyperlink_fields = []
        for field in self.fields:
            if len(field.instructions) == 1 and field.instructions[0][0] == 'HYPERLINK':
                hl = parse_hyperlink(field.instructions[0][1], log)
                if hl:
                    if 'target' in hl and hl['target'] is None:
                        hl['target'] = '_blank'
                    all_runs = []
                    current_runs = []
                    # We only handle spans in a single paragraph
                    # being wrapped in <a>
                    for x in field.contents:
                        if x.tag.endswith('}p'):
                            if current_runs:
                                all_runs.append(current_runs)
                            current_runs = []
                        elif x.tag.endswith('}r'):
                            current_runs.append(x)
                    if current_runs:
                        all_runs.append(current_runs)
                    for runs in all_runs:
                        self.hyperlink_fields.append((hl, runs))


