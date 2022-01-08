#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from calibre.ebooks.docx.index import process_index, polish_index_markup
from polyglot.builtins import iteritems, native_string_type


class Field:

    def __init__(self, start):
        self.start = start
        self.end = None
        self.contents = []
        self.buf = []
        self.instructions = None
        self.name = None

    def add_instr(self, elem):
        self.add_raw(elem.text)

    def add_raw(self, raw):
        if not raw:
            return
        if self.name is None:
            # There are cases where partial index entries end with
            # a significant space, along the lines of
            # <>Summary <>  ...  <>Hearing<>.
            # No known examples of starting with a space yet.
            # self.name, raw = raw.strip().partition(' ')[0::2]
            self.name, raw = raw.lstrip().partition(' ')[0::2]
        self.buf.append(raw)

    def finalize(self):
        self.instructions = ''.join(self.buf)
        del self.buf


WORD, FLAG = 0, 1
scanner = re.Scanner([
    (r'\\\S{1}', lambda s, t: (t, FLAG)),  # A flag of the form \x
    (r'"[^"]*"', lambda s, t: (t[1:-1], WORD)),  # Quoted word
    (r'[^\s\\"]\S*', lambda s, t: (t, WORD)),  # A non-quoted word, must not start with a backslash or a space or a quote
    (r'\s+', None),
], flags=re.DOTALL)

null = object()


def parser(name, field_map, default_field_name=None):

    field_map = dict(x.split(':') for x in field_map.split())

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

    parse.__name__ = native_string_type('parse_' + name)

    return parse


parse_hyperlink = parser('hyperlink',
    'l:anchor m:image-map n:target o:title t:target', 'url')

parse_xe = parser('xe',
    'b:bold i:italic f:entry-type r:page-range-bookmark t:page-number-text y:yomi', 'text')

parse_index = parser('index',
    'b:bookmark c:columns-per-page d:sequence-separator e:first-page-number-separator'
    ' f:entry-type g:page-range-separator h:heading k:crossref-separator'
    ' l:page-number-separator p:letter-range s:sequence-name r:run-together y:yomi z:langcode')

parse_ref = parser('ref',
    'd:separator f:footnote h:hyperlink n:number p:position r:relative-number t:suppress w:number-full-context')

parse_noteref = parser('noteref',
                   'f:footnote h:hyperlink p:position')


class Fields:

    def __init__(self, namespace):
        self.namespace = namespace
        self.fields = []
        self.index_bookmark_counter = 0
        self.index_bookmark_prefix = 'index-'

    def __call__(self, doc, log):
        all_ids = frozenset(self.namespace.XPath('//*/@w:id')(doc))
        c = 0
        while self.index_bookmark_prefix in all_ids:
            c += 1
            self.index_bookmark_prefix = self.index_bookmark_prefix.replace('-', '%d-' % c)
        stack = []
        for elem in self.namespace.XPath(
            '//*[name()="w:p" or name()="w:r" or'
            ' name()="w:instrText" or'
            ' (name()="w:fldChar" and (@w:fldCharType="begin" or @w:fldCharType="end") or'
            ' name()="w:fldSimple")]')(doc):
            if elem.tag.endswith('}fldChar'):
                typ = self.namespace.get(elem, 'w:fldCharType')
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
            elif elem.tag.endswith('}fldSimple'):
                field = Field(elem)
                instr = self.namespace.get(elem, 'w:instr')
                if instr:
                    field.add_raw(instr)
                    self.fields.append(field)
                    for r in self.namespace.XPath('descendant::w:r')(elem):
                        field.contents.append(r)
            else:
                if stack:
                    stack[-1].contents.append(elem)

        field_types = ('hyperlink', 'xe', 'index', 'ref', 'noteref')
        parsers = {x.upper():getattr(self, 'parse_'+x) for x in field_types}
        parsers.update({x:getattr(self, 'parse_'+x) for x in field_types})
        field_parsers = {f.upper():globals()['parse_%s' % f] for f in field_types}
        field_parsers.update({f:globals()['parse_%s' % f] for f in field_types})

        for f in field_types:
            setattr(self, '%s_fields' % f, [])
        unknown_fields = {'TOC', 'toc', 'PAGEREF', 'pageref'}  # The TOC and PAGEREF fields are handled separately

        for field in self.fields:
            field.finalize()
            if field.instructions:
                func = parsers.get(field.name, None)
                if func is not None:
                    func(field, field_parsers[field.name], log)
                elif field.name not in unknown_fields:
                    log.warn('Encountered unknown field: %s, ignoring it.' % field.name)
                    unknown_fields.add(field.name)

    def get_runs(self, field):
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
        return all_runs

    def parse_hyperlink(self, field, parse_func, log):
        # Parse hyperlink fields
        hl = parse_func(field.instructions, log)
        if hl:
            if 'target' in hl and hl['target'] is None:
                hl['target'] = '_blank'
            for runs in self.get_runs(field):
                self.hyperlink_fields.append((hl, runs))

    def parse_ref(self, field, parse_func, log):
        ref = parse_func(field.instructions, log)
        dest = ref.get(None, None)
        if dest is not None and 'hyperlink' in ref:
            for runs in self.get_runs(field):
                self.hyperlink_fields.append(({'anchor':dest}, runs))
        else:
            log.warn(f'Unsupported reference field ({field.name}), ignoring: {ref!r}')

    parse_noteref = parse_ref

    def parse_xe(self, field, parse_func, log):
        # Parse XE fields
        if None in (field.start, field.end):
            return
        xe = parse_func(field.instructions, log)
        if xe:
            # We insert a synthetic bookmark around this index item so that we
            # can link to it later
            def WORD(x):
                return self.namespace.expand('w:' + x)
            self.index_bookmark_counter += 1
            bmark = xe['anchor'] = '%s%d' % (self.index_bookmark_prefix, self.index_bookmark_counter)
            p = field.start.getparent()
            bm = p.makeelement(WORD('bookmarkStart'))
            bm.set(WORD('id'), bmark), bm.set(WORD('name'), bmark)
            p.insert(p.index(field.start), bm)
            p = field.end.getparent()
            bm = p.makeelement(WORD('bookmarkEnd'))
            bm.set(WORD('id'), bmark)
            p.insert(p.index(field.end) + 1, bm)
            xe['start_elem'] = field.start
            self.xe_fields.append(xe)

    def parse_index(self, field, parse_func, log):
        if not field.contents:
            return
        idx = parse_func(field.instructions, log)
        hyperlinks, blocks = process_index(field, idx, self.xe_fields, log, self.namespace.XPath, self.namespace.expand)
        if not blocks:
            return
        for anchor, run in hyperlinks:
            self.hyperlink_fields.append(({'anchor':anchor}, [run]))

        self.index_fields.append((idx, blocks))

    def polish_markup(self, object_map):
        if not self.index_fields:
            return
        rmap = {v:k for k, v in iteritems(object_map)}
        for idx, blocks in self.index_fields:
            polish_index_markup(idx, [rmap[b] for b in blocks])


def test_parse_fields(return_tests=False):
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
    if return_tests:
        return suite
    unittest.TextTestRunner(verbosity=4).run(suite)


if __name__ == '__main__':
    test_parse_fields()
