#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

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
    ans = fs(string_or_bytes, parser=create_parser(recover))
    if ans is None and recover:
        # this happens on windows where if string_or_bytes is unicode and
        # contains non-BMP chars lxml chokes
        if not isinstance(string_or_bytes, bytes):
            string_or_bytes = string_or_bytes.encode('utf-8')
            ans = fs(string_or_bytes, parser=create_parser(True, encoding='utf-8'))
            if ans is not None:
                return ans
        ans = fs(string_or_bytes, parser=create_parser(False))
    return ans


def find_tests():
    import unittest, tempfile, os
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
                    root = safe_xml_fromstring(raw) if safe else etree.fromstring(raw)
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


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
