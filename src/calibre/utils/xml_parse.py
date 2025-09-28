#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import sys

from lxml import etree

# resolving of SYSTEM entities is turned off as entities can cause
# reads of local files, for example:
# <!DOCTYPE foo [ <!ENTITY passwd SYSTEM "file:///etc/passwd" >]>

fs = etree.fromstring


class Resolver(etree.Resolver):

    def resolve(self, url, id, context):
        return self.resolve_string('', context)


def create_parser(recover, encoding=None):
    parser = etree.XMLParser(recover=recover, no_network=True, encoding=encoding)
    parser.resolvers.add(Resolver())
    return parser


def safe_xml_fromstring(string_or_bytes, recover=True):
    if isinstance(string_or_bytes, str):
        # libxml2 anyway converts to UTF-8 to parse internally
        # and does so with bugs, see
        # https://bugs.launchpad.net/lxml/+bug/2125756
        string_or_bytes = string_or_bytes.encode('utf-8')
    return fs(string_or_bytes, parser=create_parser(recover))


def unsafe_xml_fromstring(string_or_bytes):
    parser = etree.XMLParser(resolve_entities=True)
    return fs(string_or_bytes, parser=parser)


def find_tests():
    import os
    import tempfile
    import unittest

    from calibre.constants import iswindows

    class TestXMLParse(unittest.TestCase):

        def setUp(self):
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                tf.write(b'external')
                self.temp_file = os.path.abspath(tf.name)
            if iswindows:
                from calibre_extensions.winutil import get_long_path_name
                self.temp_file = get_long_path_name(self.temp_file)

        def tearDown(self):
            os.remove(self.temp_file)

        def test_safe_xml_fromstring(self):
            templ = '''<!DOCTYPE foo [ <!ENTITY e {id} "{val}" > ]><r>&e;</r>'''
            external = 'file:///' + self.temp_file.replace(os.sep, '/')

            def t(tid, val, expected, safe=True):
                raw = templ.format(id=tid, val=val)
                err = None
                try:
                    root = safe_xml_fromstring(raw) if safe else unsafe_xml_fromstring(raw)
                except Exception as e:
                    err = str(e)
                    root = None
                got = getattr(root, 'text', object())
                self.assertEqual(got, expected, f'Unexpected result parsing: {raw!r}, got: {got!r} expected: {expected!r} with XML parser error: {err}')

            t('SYSTEM', external, 'external', safe=False)

            for eid, val, expected in (
                ('', 'normal entity', 'normal entity'),
                ('', external, external),

                ('SYSTEM', external, None),
                ('SYSTEM', 'http://example.com', None),

                ('PUBLIC', external, None),
                ('PUBLIC', 'http://example.com', None),
            ):
                t(eid, val, expected)

        def test_lxml_unicode_parsing(self):
            from calibre.ebooks.chardet import xml_to_unicode
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'unicode-test.opf'), 'rb') as f:
                raw = f.read()
            text = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True, assume_utf8=True)[0]
            self.assertIsNotNone(safe_xml_fromstring(text))

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestXMLParse)


def develop():
    from calibre.ebooks.chardet import xml_to_unicode
    # print(etree.tostring(fs('<r/>')).decode())
    data = xml_to_unicode(open(sys.argv[-1], 'rb').read(), strip_encoding_pats=True, assume_utf8=True, resolve_entities=True)[0]
    print(etree.tostring(safe_xml_fromstring(data)).decode())


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
