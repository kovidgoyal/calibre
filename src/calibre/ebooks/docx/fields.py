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
        self.elements = []
        self.instructions = []

    def add_instr(self, elem):
        raw = elem.text
        if not raw:
            return
        name, rest = raw.strip().partition(' ')[0::2]
        self.instructions.append((name, rest.strip()))
        self.elements.append(elem)

WORD, FLAG = 0, 1
scanner = re.Scanner([
    (r'\\\S{1}', lambda s, t: (t, FLAG)),  # A flag of the form \x
    (r'"[^"]*"', lambda s, t: (t[1:-1], WORD)),  # Quoted word
    (r'[^\s\\"]\S*', lambda s, t: (t, WORD)),  # A non-quoted word, must not start with a backslash or a space or a quote
    (r'\s+', None),
], flags=re.DOTALL)

null = object()

def parser(name, field_map, default_field_name=None):

    field_map = dict((x.split(':') for x in field_map.split()))

    def parse(raw, log=None):
        ans = {}
        last_option = None
        raw = raw.replace('\\\\', '\x01').replace('\\"', '\x02')
        for token, token_type in scanner.scan(raw)[0]:
            token = token.replace('\x01', '\\').replace('\x02', '"')
            if token_type is FLAG:
                last_option = field_map.get(token[1], null)
                if last_option is not None:
                    ans[last_option] = None
            elif token_type is WORD:
                if last_option is None:
                    ans[default_field_name] = token
                else:
                    ans[last_option] = token
                    last_option = None
        ans.pop(null, None)
        return ans

    parse.__name__ = str('parse_' + name)

    return parse

parse_hyperlink = parser('hyperlink',
    'l:anchor m:image-map n:target o:title t:target', 'url')

parse_xe = parser('xe',
    'b:bold i:italic f:entry-type r:page-range-bookmark t:page-number-text y:yomi', 'text')

parse_index = parser('index',
    'b:bookmark c:columns-per-page d:sequence-separator e:first-page-number-separator'
    ' f:entry-type g:page-range-separator h:heading k:crossref-separator'
    ' p:page-number-separator r:run-together y:yomi z:langcode')

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

        field_types = ('hyperlink', 'xe', 'index')
        parsers = {x.upper():getattr(self, 'parse_'+x) for x in field_types}
        field_parsers = {f.upper():globals()['parse_%s' % f] for f in field_types}

        for f in field_types:
            setattr(self, '%s_fields' % f, [])

        for field in self.fields:
            if field.instructions:
                name = field.instructions[0][0]
                func = parsers.get(name, None)
                if func is not None:
                    func(field, field_parsers[name], log)

    def parse_hyperlink(self, field, parse_func, log):
        # Parse hyperlink fields
        if len(field.instructions) == 1:
            hl = parse_func(field.instructions[0][1], log)
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

    def parse_xe(self, field, parse_func, log):
        # Parse XE fields
        xe = parse_func(field.instructions[0][1], log)  # TODO: Handle field with multiple instructions
        if xe:
            # TODO: parse the field contents
            self.xe_fields.append(xe)

    def parse_index(self, field, parse_func, log):
        # Parse Index fields
        if len(field.instructions):
            idx = parse_func(field.instructions[0][1], log)
            # TODO: parse the field contents
            self.index_fields.append(idx)

def test_parse_fields():
    import unittest

    class TestParseFields(unittest.TestCase):

        def test_hyperlink(self):
            ae = lambda x, y: self.assertEqual(parse_hyperlink(x, None), y)
            ae(r'\l anchor1', {'anchor':'anchor1'})
            ae(r'www.calibre-ebook.com', {'url':'www.calibre-ebook.com'})
            ae(r'www.calibre-ebook.com \t target \o tt', {'url':'www.calibre-ebook.com', 'target':'target', 'title': 'tt'})
            ae(r'"c:\\Some Folder"', {'url': 'c:\\Some Folder'})
            ae(r'xxxx \y yyyy', {'url': 'xxxx'})

        def test_xe(self):
            ae = lambda x, y: self.assertEqual(parse_xe(x, None), y)
            ae(r'"some name"', {'text':'some name'})
            ae(r'name \b \i', {'text':'name', 'bold':None, 'italic':None})
            ae(r'xxx \y a', {'text':'xxx', 'yomi':'a'})

        def test_index(self):
            ae = lambda x, y: self.assertEqual(parse_index(x, None), y)
            ae(r'', {})
            ae(r'\b \c 1', {'bookmark':None, 'columns-per-page': '1'})

    suite = unittest.TestLoader().loadTestsFromTestCase(TestParseFields)
    unittest.TextTestRunner(verbosity=4).run(suite)

if __name__ == '__main__':
    test_parse_fields()
