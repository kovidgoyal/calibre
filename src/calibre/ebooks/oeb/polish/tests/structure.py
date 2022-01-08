#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from io import BytesIO
from itertools import count
from functools import partial
from zipfile import ZipFile, ZIP_STORED
import os
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.create import create_book
from calibre.ebooks.oeb.polish.cover import (
    find_cover_image, mark_as_cover, find_cover_page, mark_as_titlepage, clean_opf
)
from calibre.ebooks.oeb.polish.toc import get_toc, from_xpaths as toc_from_xpaths, get_landmarks
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.opf3 import CALIBRE_PREFIX

OPF_TEMPLATE = '''
<package xmlns="http://www.idpf.org/2007/opf" version="{ver}" prefix="calibre: %s" unique-identifier="uid">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier id="uid">test</dc:identifier>
        {metadata}
    </metadata>
    <manifest>{manifest}</manifest>
    <spine>{spine}</spine>
    <guide>{guide}</guide>
</package>''' % CALIBRE_PREFIX  # noqa


def create_manifest_item(name, data=b'', properties=None):
    return (name, data, properties)


cmi = create_manifest_item


def create_epub(manifest, spine=(), guide=(), meta_cover=None, ver=3):
    mo = []
    for name, data, properties in manifest:
        mo.append('<item id="{}" href="{}" media-type="{}" {}/>'.format(
            name, name, guess_type(name), ('properties="%s"' % properties if properties else '')))
    mo = ''.join(mo)
    metadata = ''
    if meta_cover:
        metadata = '<meta name="cover" content="%s"/>' % meta_cover
    if not spine:
        spine = [x[0] for x in manifest if guess_type(x[0]) in OEB_DOCS]
    spine = ''.join('<itemref idref="%s"/>' % name for name in spine)
    guide = ''.join(f'<reference href="{name}" type="{typ}" title="{title}"/>' for name, typ, title in guide)
    opf = OPF_TEMPLATE.format(manifest=mo, ver='%d.0'%ver, metadata=metadata, spine=spine, guide=guide)
    buf = BytesIO()
    with ZipFile(buf, 'w', ZIP_STORED) as zf:
        zf.writestr('META-INF/container.xml', b'''
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>''')
        zf.writestr('content.opf', opf.encode('utf-8'))
        for name, data, properties in manifest:
            if isinstance(data, str):
                data = data.encode('utf-8')
            zf.writestr(name, data or b'\0')
    buf.seek(0)
    return buf


counter = count()


class Structure(BaseTest):

    def create_epub(self, *args, **kw):
        n = next(counter)
        ep = os.path.join(self.tdir, str(n) + 'book.epub')
        with open(ep, 'wb') as f:
            f.write(create_epub(*args, **kw).getvalue())
        c = get_container(ep, tdir=os.path.join(self.tdir, 'container%d' % n), tweak_mode=True)
        return c

    def test_toc_detection(self):
        ep = os.path.join(self.tdir, 'book.epub')
        create_book(Metadata('Test ToC'), ep)
        c = get_container(ep, tdir=os.path.join(self.tdir, 'container'), tweak_mode=True)
        self.assertEqual(2, c.opf_version_parsed.major)
        self.assertTrue(len(get_toc(c)))
        c.opf.set('version', '3.0')
        self.assertEqual(3, c.opf_version_parsed.major)
        self.assertTrue(len(get_toc(c)))  # detect NCX toc even in epub 3 files
        c.add_file('nav.html', b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
                   b'<body><nav epub:type="toc"><ol><li><a href="start.xhtml">EPUB 3 nav</a></li></ol></nav></body></html>',
                   process_manifest_item=lambda item:item.set('properties', 'nav'))
        toc = get_toc(c)
        self.assertTrue(len(toc))
        self.assertEqual(toc.as_dict['children'][0]['title'], 'EPUB 3 nav')

        def tfx(linear, expected):
            items = ['<t{0}>{0}</t{0}>'.format(x) for x in linear]
            html = '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            html += '<body>%s</body></html>' % '\n'.join(items)
            with c.open('nav.html', 'wb') as f:
                f.write(html.encode('utf-8'))
            toc = toc_from_xpaths(c, ['//h:t'+x for x in sorted(set(linear))])

            def p(node):
                ans = ''
                if node.children:
                    ans += '['
                    for c in node.children:
                        ans += c.title + p(c)
                    ans += ']'
                return ans
            self.assertEqual('[%s]'%expected, p(toc))

        tfx('121333', '1[2]1[333]')
        tfx('1223424', '1[22[3[4]]2[4]]')
        tfx('32123', '321[2[3]]')
        tfx('123123', '1[2[3]]1[2[3]]')

    def test_landmarks_detection(self):
        c = self.create_epub([cmi('xxx.html'), cmi('a.html')], guide=[('xxx.html#moo', 'x', 'XXX'), ('a.html', '', 'YYY')], ver=2)
        self.assertEqual(2, c.opf_version_parsed.major)
        self.assertEqual([
            {'dest':'xxx.html', 'frag':'moo', 'type':'x', 'title':'XXX'}, {'dest':'a.html', 'frag':'', 'type':'', 'title':'YYY'}
        ], get_landmarks(c))
        c = self.create_epub([cmi('xxx.html'), cmi('a.html')], ver=3)
        self.assertEqual(3, c.opf_version_parsed.major)
        c.add_file('xxx/nav.html', b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
                   b'<body><nav epub:type="landmarks"><ol><li><a epub:type="x" href="../xxx.html#moo">XXX </a></li>'
                   b'<li><a href="../a.html"> YYY </a></li>'
                   b'</ol></nav></body></html>',
                   process_manifest_item=lambda item:item.set('properties', 'nav'))
        self.assertEqual([
            {'dest':'xxx.html', 'frag':'moo', 'type':'x', 'title':'XXX'}, {'dest':'a.html', 'frag':'', 'type':'', 'title':'YYY'}
        ], get_landmarks(c))

    def test_epub3_covers(self):
        # cover image
        ce = partial(self.create_epub, ver=3)
        c = ce([cmi('c.jpg')])
        self.assertIsNone(find_cover_image(c))
        c = ce([cmi('c.jpg')], meta_cover='c.jpg')
        self.assertEqual('c.jpg', find_cover_image(c))
        c = ce([cmi('c.jpg', b'z', 'cover-image'), cmi('d.jpg')], meta_cover='d.jpg')
        self.assertEqual('c.jpg', find_cover_image(c))
        mark_as_cover(c, 'd.jpg')
        self.assertEqual('d.jpg', find_cover_image(c))
        self.assertFalse(c.opf_xpath('//*/@name'))

        # title page
        c = ce([cmi('c.html'), cmi('a.html')])
        self.assertIsNone(find_cover_page(c))
        mark_as_titlepage(c, 'a.html', move_to_start=False)
        self.assertEqual('a.html', find_cover_page(c))
        self.assertEqual('c.html', next(c.spine_names)[0])
        mark_as_titlepage(c, 'a.html', move_to_start=True)
        self.assertEqual('a.html', find_cover_page(c))
        self.assertEqual('a.html', next(c.spine_names)[0])

        # clean opf of all cover information
        c = ce([cmi('c.jpg', b'z', 'cover-image'), cmi('c.html', b'', 'calibre:title-page'), cmi('d.html')],
                             meta_cover='c.jpg', guide=[('c.jpg', 'cover', ''), ('d.html', 'cover', '')])
        self.assertEqual(set(clean_opf(c)), {'c.jpg', 'c.html', 'd.html'})
        self.assertFalse(c.opf_xpath('//*/@name'))
        self.assertFalse(c.opf_xpath('//*/@type'))
        for prop in 'cover-image calibre:title-page'.split():
            self.assertEqual([], list(c.manifest_items_with_property(prop)))

    def test_epub2_covers(self):
        # cover image
        ce = partial(self.create_epub, ver=2)
        c = ce([cmi('c.jpg')])
        self.assertIsNone(find_cover_image(c))
        c = ce([cmi('c.jpg')], meta_cover='c.jpg')
        self.assertEqual('c.jpg', find_cover_image(c))
        c = ce([cmi('c.jpg'), cmi('d.jpg')], guide=[('c.jpg', 'cover', '')])
        self.assertEqual('c.jpg', find_cover_image(c))
        mark_as_cover(c, 'd.jpg')
        self.assertEqual('d.jpg', find_cover_image(c))
        self.assertEqual({'cover':'d.jpg'}, c.guide_type_map)

        # title page
        c = ce([cmi('c.html'), cmi('a.html')])
        self.assertIsNone(find_cover_page(c))
        mark_as_titlepage(c, 'a.html', move_to_start=False)
        self.assertEqual('a.html', find_cover_page(c))
        self.assertEqual('c.html', next(c.spine_names)[0])
        mark_as_titlepage(c, 'a.html', move_to_start=True)
        self.assertEqual('a.html', find_cover_page(c))
        self.assertEqual('a.html', next(c.spine_names)[0])


def find_tests():
    import unittest
    return unittest.defaultTestLoader.loadTestsFromTestCase(Structure)


def run_tests():
    from calibre.utils.run_tests import run_tests
    run_tests(find_tests)
