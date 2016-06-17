#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from collections import defaultdict
import unittest

from lxml import etree

from calibre.ebooks.metadata.opf3 import (
    parse_prefixes, reserved_prefixes, expand_prefix, read_identifiers, read_metadata
)

TEMPLATE = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">{metadata}</metadata></package>'''  # noqa

class TestOPF3(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def get_opf(self, metadata=''):
        return etree.fromstring(TEMPLATE.format(metadata=metadata))

    def test_prefix_parsing(self):
        self.ae(parse_prefixes('foaf: http://xmlns.com/foaf/spec/\n dbp: http://dbpedia.org/ontology/'),
                {'foaf':'http://xmlns.com/foaf/spec/', 'dbp': 'http://dbpedia.org/ontology/'})
        for raw, expanded in (
                ('onix:xxx', reserved_prefixes['onix'] + ':xxx'),
                ('xxx:onix', 'xxx:onix'),
                ('xxx', 'xxx'),
        ):
            self.ae(expand_prefix(raw, reserved_prefixes), expanded)

    def test_identifiers(self):
        def idt(val, scheme=None):
            return '<dc:identifier {scheme}>{val}</dc:identifier>'.format(scheme=('opf:scheme="%s"'%scheme if scheme else ''), val=val)
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
            self.ae(result, dict(read_identifiers(self.get_opf(m), reserved_prefixes, defaultdict(list))))
        mi = read_metadata(self.get_opf(
            metadata=idt('a:1')+idt('a:2')+idt('calibre:x')+idt('uuid:y')))
        self.ae(mi.application_id, 'x')

class TestRunner(unittest.main):

    def createTests(self):
        tl = unittest.TestLoader()
        self.test = tl.loadTestsFromTestCase(TestOPF3)

def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)

if __name__ == '__main__':
    run(verbosity=4)
