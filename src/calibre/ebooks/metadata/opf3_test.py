#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from collections import defaultdict
from io import BytesIO
import unittest

from calibre.ebooks.metadata.book import ALL_METADATA_FIELDS
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.metadata.opf3 import (
    parse_prefixes, reserved_prefixes, expand_prefix, read_identifiers,
    read_metadata, set_identifiers, XPath, set_application_id, read_title,
    read_refines, set_title, read_title_sort, read_languages, set_languages,
    read_authors, Author, set_authors, ensure_prefix, read_prefixes,
    read_book_producers, set_book_producers, read_timestamp, set_timestamp,
    read_pubdate, set_pubdate, CALIBRE_PREFIX, read_last_modified, read_comments,
    set_comments, read_publisher, set_publisher, read_tags, set_tags, read_rating,
    set_rating, read_series, set_series, read_user_metadata, set_user_metadata,
    read_author_link_map, read_user_categories, set_author_link_map, set_user_categories,
    apply_metadata, read_raster_cover, ensure_is_only_raster_cover
)
# This import is needed to prevent a test from running slowly
from calibre.ebooks.oeb.polish.pretty import pretty_opf, pretty_xml_tree  # noqa

read_author_link_map, read_user_categories, set_author_link_map, set_user_categories

TEMPLATE = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" prefix="calibre: %s" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">{metadata}</metadata><manifest>{manifest}</manifest></package>''' % CALIBRE_PREFIX  # noqa
default_refines = defaultdict(list)


class TestOPF3(unittest.TestCase):

    ae = unittest.TestCase.assertEqual

    def get_opf(self, metadata='', manifest=''):
        return safe_xml_fromstring(TEMPLATE.format(metadata=metadata, manifest=manifest))

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
        set_application_id(root, {}, default_refines, 'y')
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
        set_application_id(root, {}, default_refines, 'y')
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
        root = self.get_opf('''<dc:creator>a  b</dc:creator><dc:creator opf:role="aut">c d</dc:creator>''')
        self.ae([Author('c d', None)], rl(root))
        self.ae(authors, st(root, authors))
        root = self.get_opf('''<dc:creator id="1">a  b</dc:creator>'''
                            '''<meta refines="#1" property="role">aut</meta>'''
                            '''<meta refines="#1" property="role">cow</meta>''')
        self.ae([Author('a b', None)], rl(root))
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
        self.ae(['12'], st(root, ['12']))
    # }}}

    def test_dates(self):  # {{{
        from calibre.utils.date import utcnow

        def rl(root):
            p, r = read_prefixes(root), read_refines(root)
            return read_pubdate(root, p, r), read_timestamp(root, p, r)

        def st(root, pd, ts):
            p, r = read_prefixes(root), read_refines(root)
            set_pubdate(root, p, r, pd)
            set_timestamp(root, p, r, ts)
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
        q = n.replace(microsecond=0)
        self.ae(st(root, n, n), (n, q))
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

    def test_raster_cover(self):  # {{{
        def rt(root):
            return read_raster_cover(root, read_prefixes(root), read_refines(root))
        root = self.get_opf('<meta name="cover" content="cover"/>', '<item id="cover" media-type="image/jpeg" href="x.jpg"/>')
        self.ae('x.jpg', rt(root))
        root = self.get_opf('<meta name="cover" content="cover"/>',
                            '<item id="cover" media-type="image/jpeg" href="x.jpg"/><item media-type="image/jpeg" href="y.jpg" properties="cover-image"/>')
        self.ae('y.jpg', rt(root))
        ensure_is_only_raster_cover(root, read_prefixes(root), read_refines(root), 'x.jpg')
        self.ae('x.jpg', rt(root))
        self.ae(['x.jpg'], root.xpath('//*[@properties="cover-image"]/@href'))
        self.assertFalse(root.xpath('//*[@name]'))
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

    def test_user_metadata(self):  # {{{
        def rt(root, name):
            f = globals()['read_' + name]
            return f(root, read_prefixes(root), read_refines(root))

        def st(root, name, val):
            f = globals()['set_' + name]
            f(root, read_prefixes(root), read_refines(root), val)
            return rt(root, name)
        for name in 'author_link_map user_categories'.split():
            root = self.get_opf('''<meta name="calibre:%s" content='{"1":1}'/>''' % name)
            self.ae({'1':1}, rt(root, name))
            root = self.get_opf('''<meta name="calibre:%s" content='{"1":1}'/><meta property="calibre:%s">{"2":2}</meta>''' % (name, name))
            self.ae({'2':2}, rt(root, name))
            self.ae({'3':3}, st(root, name, {3:3}))

        def ru(root):
            return read_user_metadata(root, read_prefixes(root), read_refines(root))

        def su(root, val):
            set_user_metadata(root, read_prefixes(root), read_refines(root), val)
            return ru(root)
        root = self.get_opf('''<meta name="calibre:user_metadata:#a" content='{"1":1}'/>''')
        self.ae({'#a': {'1': 1, 'is_multiple': dict()}}, ru(root))
        root = self.get_opf('''<meta name="calibre:user_metadata:#a" content='{"1":1}'/>'''
                            '''<meta property="calibre:user_metadata">{"#b":{"2":2}}</meta>''')
        self.ae({'#b': {'2': 2, 'is_multiple': dict()}}, ru(root))
        self.ae({'#c': {'3': 3, 'is_multiple': {}, 'is_multiple2': dict()}}, su(root, {'#c':{'3':3}}))

    # }}}

    def test_against_opf2(self):  # {{{
        # opf2 {{{
        raw = '''<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier opf:scheme="calibre" id="calibre_id">1698</dc:identifier>
        <dc:identifier opf:scheme="uuid" id="uuid_id">27106d11-0721-44bc-bcdd-2840f31aaec0</dc:identifier>
        <dc:title>DOCX Demo</dc:title>
        <dc:creator opf:file-as="Goyal, Kovid" opf:role="aut">Kovid Goyal</dc:creator>
        <dc:contributor opf:file-as="calibre" opf:role="bkp">calibre (2.57.1) [http://calibre-ebook.com]</dc:contributor>
        <dc:date>2016-02-17T10:53:08+00:00</dc:date>
        <dc:description>Demonstration of DOCX support in calibre</dc:description>
        <dc:publisher>Kovid Goyal</dc:publisher>
        <dc:identifier opf:scheme="K">xxx</dc:identifier>
        <dc:language>eng</dc:language>
        <dc:subject>calibre</dc:subject>
        <dc:subject>conversion</dc:subject>
        <dc:subject>docs</dc:subject>
        <dc:subject>ebook</dc:subject>
        <meta content="{&quot;Kovid Goyal&quot;: &quot;&quot;}" name="calibre:author_link_map"/>
        <meta content="Demos" name="calibre:series"/>
        <meta content="1" name="calibre:series_index"/>
        <meta content="10" name="calibre:rating"/>
        <meta content="2015-12-11T16:28:36+00:00" name="calibre:timestamp"/>
        <meta content="DOCX Demo" name="calibre:title_sort"/>
        <meta content="{&quot;crew.crow&quot;: [], &quot;crew.moose&quot;: [], &quot;crew&quot;: []}" name="calibre:user_categories"/>
        <meta name="calibre:user_metadata:#number" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;Number&quot;,
        &quot;rec_index&quot;: 29, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 12, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;number_format&quot;: null}, &quot;search_terms&quot;:
        [&quot;#number&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;int&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: 31, &quot;is_custom&quot;:
        true, &quot;label&quot;: &quot;number&quot;, &quot;table&quot;:
        &quot;custom_column_12&quot;, &quot;is_multiple&quot;: null,
        &quot;is_category&quot;: false}"/>
        <meta name="calibre:user_metadata:#genre" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;Genre&quot;,
        &quot;rec_index&quot;: 26, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 9, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;use_decorations&quot;: 0}, &quot;search_terms&quot;:
        [&quot;#genre&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;text&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: &quot;Demos&quot;,
        &quot;is_custom&quot;: true, &quot;label&quot;: &quot;genre&quot;,
        &quot;table&quot;: &quot;custom_column_9&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: true}"/>
        <meta name="calibre:user_metadata:#commetns"
        content="{&quot;kind&quot;: &quot;field&quot;, &quot;column&quot;:
        &quot;value&quot;, &quot;is_csp&quot;: false, &quot;name&quot;:
        &quot;My Comments&quot;, &quot;rec_index&quot;: 23,
        &quot;#extra#&quot;: null, &quot;colnum&quot;: 13,
        &quot;is_multiple2&quot;: {}, &quot;category_sort&quot;:
        &quot;value&quot;, &quot;display&quot;: {}, &quot;search_terms&quot;:
        [&quot;#commetns&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;comments&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;:
        &quot;&lt;div&gt;&lt;b&gt;&lt;i&gt;Testing&lt;/i&gt;&lt;/b&gt; extra
        &lt;font
        color=\\&quot;#aa0000\\&quot;&gt;comments&lt;/font&gt;&lt;/div&gt;&quot;,
        &quot;is_custom&quot;: true, &quot;label&quot;: &quot;commetns&quot;,
        &quot;table&quot;: &quot;custom_column_13&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: false}"/>
        <meta name="calibre:user_metadata:#formats" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;Formats&quot;,
        &quot;rec_index&quot;: 25, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 4, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;composite_template&quot;: &quot;{formats}&quot;,
        &quot;contains_html&quot;: false, &quot;use_decorations&quot;: 0,
        &quot;composite_sort&quot;: &quot;text&quot;,
        &quot;make_category&quot;: false}, &quot;search_terms&quot;:
        [&quot;#formats&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;composite&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: &quot;AZW3, DOCX, EPUB&quot;,
        &quot;is_custom&quot;: true, &quot;label&quot;: &quot;formats&quot;,
        &quot;table&quot;: &quot;custom_column_4&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: false}"/>
        <meta name="calibre:user_metadata:#rating" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Rating&quot;,
        &quot;rec_index&quot;: 30, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 1, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;: {},
        &quot;search_terms&quot;: [&quot;#rating&quot;],
        &quot;is_editable&quot;: true, &quot;datatype&quot;:
        &quot;rating&quot;, &quot;link_column&quot;: &quot;value&quot;,
        &quot;#value#&quot;: 10, &quot;is_custom&quot;: true,
        &quot;label&quot;: &quot;rating&quot;, &quot;table&quot;:
        &quot;custom_column_1&quot;, &quot;is_multiple&quot;: null,
        &quot;is_category&quot;: true}"/>
        <meta name="calibre:user_metadata:#series" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Series2&quot;,
        &quot;rec_index&quot;: 31, &quot;#extra#&quot;: 1.0,
        &quot;colnum&quot;: 5, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;: {},
        &quot;search_terms&quot;: [&quot;#series&quot;],
        &quot;is_editable&quot;: true, &quot;datatype&quot;:
        &quot;series&quot;, &quot;link_column&quot;: &quot;value&quot;,
        &quot;#value#&quot;: &quot;s&quot;, &quot;is_custom&quot;: true,
        &quot;label&quot;: &quot;series&quot;, &quot;table&quot;:
        &quot;custom_column_5&quot;, &quot;is_multiple&quot;: null,
        &quot;is_category&quot;: true}"/>
        <meta name="calibre:user_metadata:#tags" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Tags&quot;,
        &quot;rec_index&quot;: 33, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 11, &quot;is_multiple2&quot;:
        {&quot;ui_to_list&quot;: &quot;,&quot;, &quot;cache_to_list&quot;:
        &quot;|&quot;, &quot;list_to_ui&quot;: &quot;, &quot;},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;is_names&quot;: false, &quot;description&quot;: &quot;A tag like
        column for me&quot;}, &quot;search_terms&quot;: [&quot;#tags&quot;],
        &quot;is_editable&quot;: true, &quot;datatype&quot;: &quot;text&quot;,
        &quot;link_column&quot;: &quot;value&quot;, &quot;#value#&quot;:
        [&quot;t1&quot;, &quot;t2&quot;], &quot;is_custom&quot;: true,
        &quot;label&quot;: &quot;tags&quot;, &quot;table&quot;:
        &quot;custom_column_11&quot;, &quot;is_multiple&quot;: &quot;|&quot;,
        &quot;is_category&quot;: true}"/>
        <meta name="calibre:user_metadata:#yesno" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;Yes/No&quot;,
        &quot;rec_index&quot;: 34, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 7, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;: {},
        &quot;search_terms&quot;: [&quot;#yesno&quot;],
        &quot;is_editable&quot;: true, &quot;datatype&quot;: &quot;bool&quot;,
        &quot;link_column&quot;: &quot;value&quot;, &quot;#value#&quot;: false,
        &quot;is_custom&quot;: true, &quot;label&quot;: &quot;yesno&quot;,
        &quot;table&quot;: &quot;custom_column_7&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: false}"/>
        <meta name="calibre:user_metadata:#myenum" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Enum&quot;,
        &quot;rec_index&quot;: 28, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 6, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;enum_colors&quot;: [], &quot;enum_values&quot;:
        [&quot;One&quot;, &quot;Two&quot;, &quot;Three&quot;],
        &quot;use_decorations&quot;: 0}, &quot;search_terms&quot;:
        [&quot;#myenum&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;enumeration&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: &quot;Two&quot;,
        &quot;is_custom&quot;: true, &quot;label&quot;: &quot;myenum&quot;,
        &quot;table&quot;: &quot;custom_column_6&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: true}"/>
        <meta name="calibre:user_metadata:#isbn" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;ISBN&quot;,
        &quot;rec_index&quot;: 27, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 3, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;composite_template&quot;:
        &quot;{identifiers:select(isbn)}&quot;, &quot;contains_html&quot;:
        false, &quot;use_decorations&quot;: 0, &quot;composite_sort&quot;:
        &quot;text&quot;, &quot;make_category&quot;: false},
        &quot;search_terms&quot;: [&quot;#isbn&quot;], &quot;is_editable&quot;:
        true, &quot;datatype&quot;: &quot;composite&quot;,
        &quot;link_column&quot;: &quot;value&quot;, &quot;#value#&quot;:
        &quot;&quot;, &quot;is_custom&quot;: true, &quot;label&quot;:
        &quot;isbn&quot;, &quot;table&quot;: &quot;custom_column_3&quot;,
        &quot;is_multiple&quot;: null, &quot;is_category&quot;: false}"/>
        <meta name="calibre:user_metadata:#authors" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Authors&quot;,
        &quot;rec_index&quot;: 22, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 10, &quot;is_multiple2&quot;:
        {&quot;ui_to_list&quot;: &quot;&amp;&quot;, &quot;cache_to_list&quot;:
        &quot;|&quot;, &quot;list_to_ui&quot;: &quot; &amp; &quot;},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;is_names&quot;: true}, &quot;search_terms&quot;:
        [&quot;#authors&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;text&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: [&quot;calibre, Kovid
        Goyal&quot;], &quot;is_custom&quot;: true, &quot;label&quot;:
        &quot;authors&quot;, &quot;table&quot;: &quot;custom_column_10&quot;,
        &quot;is_multiple&quot;: &quot;|&quot;, &quot;is_category&quot;:
        true}"/>
        <meta name="calibre:user_metadata:#date" content="{&quot;kind&quot;:
        &quot;field&quot;, &quot;column&quot;: &quot;value&quot;,
        &quot;is_csp&quot;: false, &quot;name&quot;: &quot;My Date&quot;,
        &quot;rec_index&quot;: 24, &quot;#extra#&quot;: null,
        &quot;colnum&quot;: 2, &quot;is_multiple2&quot;: {},
        &quot;category_sort&quot;: &quot;value&quot;, &quot;display&quot;:
        {&quot;date_format&quot;: &quot;dd-MM-yyyy&quot;,
        &quot;description&quot;: &quot;&quot;}, &quot;search_terms&quot;:
        [&quot;#date&quot;], &quot;is_editable&quot;: true,
        &quot;datatype&quot;: &quot;datetime&quot;, &quot;link_column&quot;:
        &quot;value&quot;, &quot;#value#&quot;: {&quot;__value__&quot;:
        &quot;2016-02-17T10:54:15+00:00&quot;, &quot;__class__&quot;:
        &quot;datetime.datetime&quot;}, &quot;is_custom&quot;: true,
        &quot;label&quot;: &quot;date&quot;, &quot;table&quot;:
        &quot;custom_column_2&quot;, &quot;is_multiple&quot;: null,
        &quot;is_category&quot;: false}"/>
    </metadata><manifest><item href="start.html" media-type="text/html" id="m1"/></manifest><spine><itemref idref="m1"/></spine>
</package>'''  # }}}

        def compare_metadata(mi2, mi3):
            self.ae(mi2.get_all_user_metadata(False), mi3.get_all_user_metadata(False))
            for field in ALL_METADATA_FIELDS:
                if field not in 'manifest spine':
                    v2, v3 = getattr(mi2, field, None), getattr(mi3, field, None)
                    self.ae(v2, v3, '%s: %r != %r' % (field, v2, v3))

        mi2 = OPF(BytesIO(raw.encode('utf-8'))).to_book_metadata()
        root = safe_xml_fromstring(raw)
        root.set('version', '3.0')
        mi3, _, raster_cover, first_spine_item  = read_metadata(root, return_extra_data=True)
        self.assertIsNone(raster_cover)
        self.ae('start.html', first_spine_item)
        compare_metadata(mi2, mi3)
        apply_metadata(root, mi3, force_identifiers=True)
        nmi = read_metadata(root)
        compare_metadata(mi3, nmi)
        mi3.tags = []
        mi3.set('#tags', [])
        mi3.set('#number', 0)
        mi3.set('#commetns', '')
        apply_metadata(root, mi3, update_timestamp=True)
        self.assertFalse(root.xpath('//*/@name'))
        nmi = read_metadata(root)
        self.assertEqual(mi2.tags, nmi.tags)
        self.assertEqual(mi2.get('#tags'), nmi.get('#tags'))
        self.assertEqual(mi2.get('#commetns'), nmi.get('#commetns'))
        self.assertEqual(0, nmi.get('#number'))
        apply_metadata(root, mi3, apply_null=True)
        nmi = read_metadata(root)
        self.assertFalse(nmi.tags)
        self.assertFalse(nmi.get('#tags'))
        self.assertFalse(nmi.get('#commetns'))
        self.assertIsNone(apply_metadata(root, mi3, cover_data=b'x', cover_prefix='xxx', add_missing_cover=False))
        self.ae('xxx/cover.jpg', apply_metadata(root, mi3, cover_data=b'x', cover_prefix='xxx'))
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
