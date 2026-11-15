#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, maskshell fork

from lxml import etree

from collections import OrderedDict

from calibre.ebooks.oeb.base import XHTML_NS
from calibre.ebooks.oeb.polish.split import do_split, partition_by_body_siblings
from calibre.ebooks.oeb.polish.tests.base import BaseTest
from calibre.ebooks.oeb.transforms.split import resolve_page_break_elements
from calibre.utils.logging import DevNull


def _flat_book_html(num_chapters: int = 5, paras_per_chapter: int = 3) -> etree._ElementTree:
    parts = ['<html xmlns="%s"><head><title>t</title></head><body>' % XHTML_NS, '<h1 id="title">Book</h1>']
    for i in range(1, num_chapters + 1):
        parts.append(f'<h3 id="c{i}">Chapter {i}</h3>')
        for j in range(paras_per_chapter):
            parts.append(f'<p>para {i}.{j} text</p>')
    parts.append('</body></html>')
    root = etree.fromstring(''.join(parts).encode('utf-8'))
    return root.getroottree()


class TestSiblingPartition(BaseTest):
    def test_partition_by_body_siblings_cuts_at_headings(self) -> None:
        tree = _flat_book_html(4)
        body = tree.getroot().find(f'{{{XHTML_NS}}}body')
        assert body is not None
        h3s = body.xpath('.//*[local-name()="h3"]')
        self.assertEqual(4, len(h3s))
        parts = partition_by_body_siblings(tree, h3s[1:], DevNull(), before=True)
        self.assertIsNotNone(parts)
        assert parts is not None
        # preamble+c1, c2, c3, c4
        self.assertEqual(4, len(parts))
        texts = []
        for part in parts:
            b = part.getroot().find(f'{{{XHTML_NS}}}body')
            assert b is not None
            texts.append(''.join(b.itertext()))
        self.assertIn('Chapter 1', texts[0])
        self.assertIn('Chapter 2', texts[1])
        self.assertNotIn('Chapter 2', texts[0])
        self.assertIn('Chapter 4', texts[-1])

    def test_partition_returns_none_for_non_body_descendant_gap(self) -> None:
        html = (
            f'<html xmlns="{XHTML_NS}"><head><title>t</title></head><body>'
            '<div><div><h2 id="x">Nested</h2><p>a</p></div></div>'
            '<p>after</p></body></html>'
        )
        tree = etree.fromstring(html.encode()).getroottree()
        # Point inside nested divs still maps to a body child (outer div) — should succeed.
        h2 = tree.getroot().xpath('//*[@id="x"]')[0]
        parts = partition_by_body_siblings(tree, [h2], DevNull(), before=True)
        self.assertIsNotNone(parts)

    def test_do_split_still_works(self) -> None:
        tree = _flat_book_html(2)
        h3 = tree.getroot().xpath('//*[@id="c2"]')[0]
        before, after = do_split(h3, DevNull(), before=True)
        bt = ''.join(before.getroot().itertext())
        at = ''.join(after.getroot().itertext())
        self.assertIn('Chapter 1', bt)
        self.assertNotIn('Chapter 2', bt)
        self.assertIn('Chapter 2', at)

    def test_resolve_page_break_elements_preserves_order(self) -> None:
        tree = _flat_book_html(4)
        root = tree.getroot()
        # Dummy patterns (unused by resolve); before flags alternate.
        ordered = OrderedDict(
            [
                ('c2', (None, True)),
                ('c4', (None, False)),
                ('c3', (None, True)),
                ('missing', (None, True)),
            ]
        )
        specs = resolve_page_break_elements(ordered, root)
        self.assertEqual(['c2', 'c4', 'c3'], [e.get('id') for e, _ in specs])
        self.assertEqual([True, False, True], [b for _, b in specs])
        parts = partition_by_body_siblings(tree, specs, DevNull())
        self.assertIsNotNone(parts)
        assert parts is not None
        self.assertGreaterEqual(len(parts), 3)
