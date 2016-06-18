#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from collections import defaultdict
import unittest

from lxml import etree

from calibre.ebooks.metadata.opf3 import (
    parse_prefixes, reserved_prefixes, expand_prefix, read_identifiers,
    read_metadata, set_identifiers, XPath, set_application_id, read_title,
    read_refines, set_title, read_title_sort
)

TEMPLATE = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">{metadata}</metadata></package>'''  # noqa
default_refines = defaultdict(list)

class TestOPF3(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def get_opf(self, metadata=''):
        return etree.fromstring(TEMPLATE.format(metadata=metadata))

    def test_prefix_parsing(self):  # {{{
        self.ae(parse_prefixes('foaf: http://xmlns.com/foaf/spec/\n dbp: http://dbpedia.org/ontology/'),
                {'foaf':'http://xmlns.com/foaf/spec/', 'dbp': 'http://dbpedia.org/ontology/'})
        for raw, expanded in (
                ('onix:xxx', reserved_prefixes['onix'] + ':xxx'),
                ('xxx:onix', 'xxx:onix'),
                ('xxx', 'xxx'),
        ):
            self.ae(expand_prefix(raw, reserved_prefixes), expanded)
    # }}}

    def test_identifiers(self):  # {{{
        def idt(val, scheme=None, iid=''):
            return '<dc:identifier id="{id}" {scheme}>{val}</dc:identifier>'.format(scheme=('opf:scheme="%s"'%scheme if scheme else ''), val=val, id=iid)
        def ri(root):
            return dict(read_identifiers(root, reserved_prefixes, default_refines))

        for m, result in (
                (idt('abc', 'ISBN'), {}),
                (idt('isbn:9780230739581'), {'isbn':['9780230739581']}),
                (idt('urn:isbn:9780230739581'), {'isbn':['9780230739581']}),
                (idt('9780230739581', 'ISBN'), {'isbn':['9780230739581']}),
                (idt('isbn:9780230739581', 'ISBN'), {'isbn':['9780230739581']}),
                (idt('key:val'), {'key':['val']}),
                (idt('url:http://x'), {'url':['http://x']}),
                (idt('a:1')+idt('a:2'), {'a':['1', '2']}),
        ):
            self.ae(result, ri(self.get_opf(m)))
        root = self.get_opf(metadata=idt('a:1')+idt('a:2')+idt('calibre:x')+idt('uuid:y'))
        mi = read_metadata(root)
        self.ae(mi.application_id, 'x')
        set_application_id(root, default_refines, 'y')
        mi = read_metadata(root)
        self.ae(mi.application_id, 'y')

        root = self.get_opf(metadata=idt('i:1', iid='uid') + idt('r:1') + idt('o:1'))
        set_identifiers(root, reserved_prefixes, default_refines, {'i':'2', 'o':'2'})
        self.ae({'i':['2', '1'], 'r':['1'], 'o':['2']}, ri(root))
        self.ae(1, len(XPath('//dc:identifier[@id="uid"]')(root)))
        root = self.get_opf(metadata=idt('i:1', iid='uid') + idt('r:1') + idt('o:1'))
        set_identifiers(root, reserved_prefixes, default_refines, {'i':'2', 'o':'2'}, force_identifiers=True)
        self.ae({'i':['2', '1'], 'o':['2']}, ri(root))
        root = self.get_opf(metadata=idt('i:1', iid='uid') + idt('r:1') + idt('o:1'))
        set_application_id(root, default_refines, 'y')
        mi = read_metadata(root)
        self.ae(mi.application_id, 'y')
    # }}}

    def test_title(self):  # {{{
        def rt(root):
            return read_title(root, reserved_prefixes, read_refines(root))
        def st(root, title, title_sort=None):
            set_title(root, reserved_prefixes, read_refines(root), title, title_sort)
            return rt(root)
        root = self.get_opf('''<dc:title/><dc:title id='t'>xxx</dc:title>''')
        self.ae(rt(root), 'xxx')
        self.ae(st(root, 'abc', 'cba'), 'abc')
        self.ae(read_title_sort(root, reserved_prefixes, read_refines(root)), 'cba')
        root = self.get_opf('''<dc:title>yyy</dc:title><dc:title id='t'>x  xx
            </dc:title><meta refines='#t' property='title-type'>main</meta><meta name="calibre:title_sort" content="sorted"/>''')
        self.ae(rt(root), 'x xx')
        self.ae(read_title_sort(root, reserved_prefixes, read_refines(root)), 'sorted')
        self.ae(st(root, 'abc'), 'abc')
    # }}}

# Run tests {{{

class TestRunner(unittest.main):

    def createTests(self):
        tl = unittest.TestLoader()
        self.test = tl.loadTestsFromTestCase(TestOPF3)

def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)

if __name__ == '__main__':
    run(verbosity=4)
# }}}
