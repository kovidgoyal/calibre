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
    read_refines, set_title, read_title_sort, read_languages, set_languages,
    read_authors, Author, set_authors, ensure_prefix, read_prefixes,
    read_book_producers, set_book_producers, read_timestamp, set_timestamp,
    read_pubdate, set_pubdate, CALIBRE_PREFIX, read_last_modified, read_comments,
    set_comments, read_publisher, set_publisher, read_tags, set_tags, read_rating,
    set_rating, read_series, set_series
)

TEMPLATE = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" prefix="calibre: %s" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">{metadata}</metadata></package>''' % CALIBRE_PREFIX  # noqa
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
            self.ae(expand_prefix(raw, reserved_prefixes.copy()), expanded)
        root = self.get_opf()
        ensure_prefix(root, read_prefixes(root), 'calibre', 'https://calibre-ebook.com')
        ensure_prefix(root, read_prefixes(root), 'marc', reserved_prefixes['marc'])
        self.ae(parse_prefixes(root.get('prefix')), {'calibre': 'https://calibre-ebook.com'})
    # }}}

    def test_identifiers(self):  # {{{
        def idt(val, scheme=None, iid=''):
            return '<dc:identifier id="{id}" {scheme}>{val}</dc:identifier>'.format(scheme=('opf:scheme="%s"'%scheme if scheme else ''), val=val, id=iid)
        def ri(root):
            return dict(read_identifiers(root, read_prefixes(root), default_refines))

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
        set_identifiers(root, read_prefixes(root), default_refines, {'i':'2', 'o':'2'})
        self.ae({'i':['2', '1'], 'r':['1'], 'o':['2']}, ri(root))
        self.ae(1, len(XPath('//dc:identifier[@id="uid"]')(root)))
        root = self.get_opf(metadata=idt('i:1', iid='uid') + idt('r:1') + idt('o:1'))
        set_identifiers(root, read_prefixes(root), default_refines, {'i':'2', 'o':'2'}, force_identifiers=True)
        self.ae({'i':['2', '1'], 'o':['2']}, ri(root))
        root = self.get_opf(metadata=idt('i:1', iid='uid') + idt('r:1') + idt('o:1'))
        set_application_id(root, default_refines, 'y')
        mi = read_metadata(root)
        self.ae(mi.application_id, 'y')
    # }}}

    def test_title(self):  # {{{
        def rt(root):
            return read_title(root, read_prefixes(root), read_refines(root))
        def st(root, title, title_sort=None):
            set_title(root, read_prefixes(root), read_refines(root), title, title_sort)
            return rt(root)
        root = self.get_opf('''<dc:title/><dc:title id='t'>xxx</dc:title>''')
        self.ae(rt(root), 'xxx')
        self.ae(st(root, 'abc', 'cba'), 'abc')
        self.ae(read_title_sort(root, read_prefixes(root), read_refines(root)), 'cba')
        root = self.get_opf('''<dc:title>yyy</dc:title><dc:title id='t'>x  xx
            </dc:title><meta refines='#t' property='title-type'>main</meta><meta name="calibre:title_sort" content="sorted"/>''')
        self.ae(rt(root), 'x xx')
        self.ae(read_title_sort(root, read_prefixes(root), read_refines(root)), 'sorted')
        self.ae(st(root, 'abc'), 'abc')
    # }}}

    def test_languages(self):  # {{{
        def rl(root):
            return read_languages(root, read_prefixes(root), read_refines(root))
        def st(root, languages):
            set_languages(root, read_prefixes(root), read_refines(root), languages)
            return rl(root)
        root = self.get_opf('''<dc:language>en-US</dc:language><dc:language>fr</dc:language>''')
        self.ae(['eng', 'fra'], rl(root))
        self.ae(st(root, ['de', 'de', 'es']), ['deu', 'spa'])
        self.ae(st(root, []), [])

    # }}}

    def test_authors(self):  # {{{
        def rl(root):
            return read_authors(root, read_prefixes(root), read_refines(root))
        def st(root, authors):
            set_authors(root, read_prefixes(root), read_refines(root), authors)
            return rl(root)
        root = self.get_opf('''<dc:creator>a  b</dc:creator>''')
        self.ae([Author('a b', None)], rl(root))
        for scheme in ('scheme="marc:relators"', ''):
            root = self.get_opf('''<dc:creator>a  b</dc:creator><dc:creator id="1">c d</dc:creator>'''
                                '''<meta refines="#1" property="role" %s>aut</meta>''' % scheme)
            self.ae([Author('c d', None)], rl(root))
        root = self.get_opf('''<dc:creator>a  b</dc:creator><dc:creator opf:role="aut">c d</dc:creator>''')
        self.ae([Author('c d', None)], rl(root))
        root = self.get_opf('''<dc:creator opf:file-as="b, a">a  b</dc:creator><dc:creator id="1">c d</dc:creator>
                                <meta refines="#1" property="file-as">d, c</meta>''')
        self.ae([Author('a b', 'b, a'), Author('c d', 'd, c')], rl(root))
        authors = [Author('x y', 'y, x'), Author('u i', None)]
        self.ae(authors, st(root, authors))
        self.ae(root.get('prefix'), 'calibre: %s' % CALIBRE_PREFIX)
    # }}}

    def test_book_producer(self):  # {{{
        def rl(root):
            return read_book_producers(root, read_prefixes(root), read_refines(root))
        def st(root, producers):
            set_book_producers(root, read_prefixes(root), read_refines(root), producers)
            return rl(root)
        for scheme in ('scheme="marc:relators"', ''):
            root = self.get_opf('''<dc:contributor>a  b</dc:contributor><dc:contributor id="1">c d</dc:contributor>'''
                                '''<meta refines="#1" property="role" %s>bkp</meta>''' % scheme)
            self.ae(['c d'], rl(root))
        root = self.get_opf('''<dc:contributor>a  b</dc:contributor><dc:contributor opf:role="bkp">c d</dc:contributor>''')
        self.ae(['c d'], rl(root))
        self.ae('12'.split(), st(root, '12'.split()))
    # }}}

    def test_dates(self):  # {{{
        from calibre.utils.date import utcnow
        def rl(root):
            return read_pubdate(root, read_prefixes(root), read_refines(root)), read_timestamp(root, read_prefixes(root), read_refines(root))
        def st(root, pd, ts):
            set_pubdate(root, read_prefixes(root), read_refines(root), pd)
            set_timestamp(root, read_prefixes(root), read_refines(root), ts)
            return rl(root)
        def ae(root, y1=None, y2=None):
            x1, x2 = rl(root)
            for x, y in ((x1, y1), (x2, y2)):
                if y is None:
                    self.assertIsNone(x)
                else:
                    self.ae(y, getattr(x, 'year', None))
        root = self.get_opf('''<dc:date>1999-3-2</dc:date><meta property="calibre:timestamp" scheme="dcterms:W3CDTF">2001</meta>''')
        ae(root, 1999, 2001)
        n = utcnow()
        self.ae(st(root, n, n), (n, n))
        root = self.get_opf('''<dc:date>1999-3-2</dc:date><meta name="calibre:timestamp" content="2001-1-1"/>''')
        ae(root, 1999, 2001)
        root = self.get_opf('''<meta property="dcterms:modified">2003</meta>''')
        self.ae(read_last_modified(root, read_prefixes(root), read_refines(root)).year, 2003)
    # }}}

    def test_comments(self):  # {{{
        def rt(root):
            return read_comments(root, read_prefixes(root), read_refines(root))
        def st(root, val):
            set_comments(root, read_prefixes(root), read_refines(root), val)
            return rt(root)
        root = self.get_opf('''<dc:description>&lt;span&gt;one&lt;/span&gt;</dc:description><dc:description> xxx</dc:description>''')
        self.ae('<span>one</span>\nxxx', rt(root))
        self.ae('<a>p</a>', st(root, '<a>p</a> '))
    # }}}

    def test_publisher(self):  # {{{
        def rt(root):
            return read_publisher(root, read_prefixes(root), read_refines(root))
        def st(root, val):
            set_publisher(root, read_prefixes(root), read_refines(root), val)
            return rt(root)
        root = self.get_opf('''<dc:publisher> one </dc:publisher><dc:publisher> xxx</dc:publisher>''')
        self.ae('one', rt(root))
        self.ae('<a>p</a>', st(root, '<a>p</a> '))
    # }}}

    def test_tags(self):  # {{{
        def rt(root):
            return read_tags(root, read_prefixes(root), read_refines(root))
        def st(root, val):
            set_tags(root, read_prefixes(root), read_refines(root), val)
            return rt(root)
        root = self.get_opf('''<dc:subject> one, two </dc:subject><dc:subject> xxx</dc:subject>''')
        self.ae('one,two,xxx'.split(','), rt(root))
        self.ae('1,2,3'.split(','), st(root, '1,2,3'.split(',')))
    # }}}

    def test_rating(self):  # {{{
        def rt(root):
            return read_rating(root, read_prefixes(root), read_refines(root))
        def st(root, val):
            set_rating(root, read_prefixes(root), read_refines(root), val)
            return rt(root)
        root = self.get_opf('''<meta name="calibre:rating" content="3"/>''')
        self.ae(3, rt(root))
        root = self.get_opf('''<meta name="calibre:rating" content="3"/><meta property="calibre:rating">5</meta>''')
        self.ae(5, rt(root))
        self.ae(1, st(root,1))
    # }}}

    def test_series(self):  # {{{
        def rt(root):
            return read_series(root, read_prefixes(root), read_refines(root))
        def st(root, val, i):
            set_series(root, read_prefixes(root), read_refines(root), val, i)
            return rt(root)
        root = self.get_opf('''<meta name="calibre:series" content="xxx"/><meta name="calibre:series_index" content="5"/>''')
        self.ae(('xxx', 5), rt(root))
        root = self.get_opf('''<meta name="calibre:series" content="xxx"/><meta name="calibre:series_index" content="5"/>'''
                            '<meta property="belongs-to-collection" id="c02">yyy</meta><meta refines="#c02" property="collection-type">series</meta>'
                            '<meta refines="#c02" property="group-position">2.1</meta>')
        self.ae(('yyy', 2.1), rt(root))
        self.ae(('zzz', 3.3), st(root, 'zzz', 3.3))
    # }}}

# Run tests {{{

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestOPF3)

class TestRunner(unittest.main):

    def createTests(self):
        self.test = suite()

def run(verbosity=4):
    TestRunner(verbosity=verbosity, exit=False)

if __name__ == '__main__':
    run(verbosity=4)
# }}}
