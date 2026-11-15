#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import re
import uuid
from collections import Counter
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from lxml import etree

from calibre.ebooks import ConversionError
from calibre.ebooks.oeb.base import TOC, XHTML, XHTML_NS, XPNSMAP, barename, xml2text
from calibre.utils.localization import _

if TYPE_CHECKING:
    import unittest
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import Manifest, OEBBook


def XPath(x: str) -> etree.XPath:
    try:
        return etree.XPath(x, namespaces=XPNSMAP)
    except etree.XPathSyntaxError:
        raise ConversionError(f'The syntax of the XPath expression {x!r} is invalid.')


def isspace(x: str | None) -> bool:
    return not x or x.replace('\xa0', '').isspace()


def at_start(elem: etree._Element) -> bool:
    "Return True if there is no content before elem"
    body = XPath('ancestor-or-self::h:body')(elem)
    if not body:
        return True
    body = body[0]
    ancestors = frozenset(XPath('ancestor::*')(elem))
    for x in body.iter():
        if x is elem:
            return True
        if hasattr(getattr(x, 'tag', None), 'rpartition') and x.tag.rpartition('}')[-1] in {'img', 'svg'}:
            return False
        if isspace(getattr(x, 'text', None)) and (x in ancestors or isspace(getattr(x, 'tail', None))):
            continue
        return False
    return False


class DetectStructure:
    def __call__(self, oeb: OEBBook, opts: Values | OptionValues) -> None:
        self.log = oeb.log
        self.oeb = oeb
        self.opts = opts
        self.log('Detecting structure...')

        self.detect_chapters()
        if self.oeb.auto_generated_toc or opts.use_auto_toc:
            orig_toc = self.oeb.toc
            self.oeb.toc = TOC()
            self.create_level_based_toc()
            if self.oeb.toc.count() < 1:
                if not opts.no_chapters_in_toc and self.detected_chapters:
                    self.create_toc_from_chapters()
                if self.oeb.toc.count() < opts.toc_threshold:
                    self.create_toc_from_links()
            if self.oeb.toc.count() < 2 and orig_toc.count() > 2:
                self.oeb.toc = orig_toc
            else:
                self.oeb.auto_generated_toc = True
                self.log(f'Auto generated TOC with {self.oeb.toc.count()} entries.')

        if opts.toc_filter is not None:
            regexp = re.compile(opts.toc_filter)
            for node in list(self.oeb.toc.iter()):
                if not node.title or regexp.search(node.title) is not None:
                    self.log('Filtering', node.title or 'empty node', 'from TOC')
                    self.oeb.toc.remove(node)

        if opts.page_breaks_before is not None:
            pb_xpath = XPath(opts.page_breaks_before)
            for item in oeb.spine:
                root = item.data
                assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
                for elem in pb_xpath(root):
                    try:
                        prev = next(elem.itersiblings(tag=etree.Element, preceding=True))
                        if barename(elem.tag) in {'h1', 'h2'} and barename(prev.tag) in {'h1', 'h2'} and (not prev.tail or not prev.tail.split()):
                            # We have two adjacent headings, do not put a page
                            # break on the second one
                            continue
                    except StopIteration:
                        pass

                    style = elem.get('style', '')
                    if style:
                        style += '; '
                    elem.set('style', style + 'page-break-before:always')

        for node in self.oeb.toc.iter():
            if not node.title or not node.title.strip():
                node.title = _('Unnamed')

        if self.opts.start_reading_at:
            self.detect_start_reading()

    def detect_start_reading(self) -> None:
        expr = self.opts.start_reading_at
        try:
            expr = XPath(expr)
        except Exception:
            self.log.warn(f'Invalid start reading at XPath expression, ignoring: {expr}')
            return
        for item in self.oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            matches = expr(root)
            if matches:
                elem = matches[0]
                eid = elem.get('id', None)
                if not eid:
                    eid = 'start_reading_at_' + str(uuid.uuid4()).replace('-', '')
                    elem.set('id', eid)
                if 'text' in self.oeb.guide:
                    self.oeb.guide.remove('text')
                self.oeb.guide.add('text', 'Start', item.href + '#' + eid)
                self.log(f'Setting start reading at position to {self.opts.start_reading_at} in {item.href}')
                return
        self.log.warn(f'Failed to find start reading at position: {self.opts.start_reading_at}')

    def get_toc_parts_for_xpath(self, expr: str) -> tuple[str, str | None]:
        # if an attribute is selected by the xpath expr then truncate it
        # from the path and instead return it as where to find the title text
        title_attribute_regex = re.compile(r'/@([-\w]+)$')
        match = title_attribute_regex.search(expr)
        if match is not None:
            return expr[0 : match.start()], match.group(1)

        return expr, None

    def detect_chapters(self) -> None:
        self.detected_chapters: list[tuple[Manifest.Item, etree._Element]] = []
        self.chapter_title_attribute: str | None = None

        def find_matches(expr: str, doc: etree._Element) -> list[etree._Element]:
            try:
                ans = XPath(expr)(doc)
                len(ans)
                return ans
            except Exception:
                self.log.warn(f'Invalid chapter expression, ignoring: {expr}')
                return []

        if self.opts.chapter:
            chapter_path, title_attribute = self.get_toc_parts_for_xpath(self.opts.chapter)
            self.chapter_title_attribute = title_attribute
            for item in self.oeb.spine:
                root = item.data
                assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
                for x in find_matches(chapter_path, root):
                    self.detected_chapters.append((item, x))

            chapter_mark = self.opts.chapter_mark
            page_break_before = 'display: block; page-break-before: always'
            page_break_after = 'display: block; page-break-after: always'
            c: Counter[Manifest.Item] = Counter()
            for item, elem in self.detected_chapters:
                c[item] += 1
                text = xml2text(elem).strip()
                text = re.sub(r'\s+', ' ', text.strip())
                self.log('\tDetected chapter:', text[:50])
                if chapter_mark == 'none':
                    continue
                if chapter_mark == 'rule':
                    mark = elem.makeelement(XHTML('hr'))
                elif chapter_mark == 'pagebreak':
                    if c[item] < 3 and at_start(elem):
                        # For the first two elements in this item, check if they
                        # are at the start of the file, in which case inserting a
                        # page break in unnecessary and can lead to extra blank
                        # pages in the PDF Output plugin. We need to use two as
                        # feedbooks epubs match both a heading tag and its
                        # containing div with the default chapter expression.
                        continue
                    mark = elem.makeelement(XHTML('div'), style=page_break_after)
                else:  # chapter_mark == 'both':
                    mark = elem.makeelement(XHTML('hr'), style=page_break_before)
                try:
                    elem.addprevious(mark)
                except TypeError:
                    self.log.exception('Failed to mark chapter')

    def create_level_based_toc(self) -> None:
        if self.opts.level1_toc is not None:
            self.add_leveled_toc_items()

    def create_toc_from_chapters(self) -> None:
        counter = self.oeb.toc.next_play_order()
        for item, elem in self.detected_chapters:
            text, href = self.elem_to_link(item, elem, self.chapter_title_attribute, counter)
            self.oeb.toc.add(text, href, play_order=counter)
            counter += 1

    def create_toc_from_links(self) -> None:
        num = 0
        for item in self.oeb.spine:
            root = item.data
            assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
            for a in XPath('//h:a[@href]')(root):
                href = a.get('href')
                try:
                    purl = urlparse(href)
                except ValueError:
                    self.log.warning('Ignoring malformed URL:', href)
                    continue
                if not purl[0] or purl[0] == 'file':
                    href, frag = purl.path, purl.fragment
                    href = item.abshref(href)
                    if frag:
                        href = f'{href}#{frag}'
                    if not self.oeb.toc.has_href(href):
                        text = xml2text(a)
                        text = text[:100].strip()
                        if not self.opts.duplicate_links_in_toc and self.oeb.toc.has_text(text):
                            continue
                        try:
                            self.oeb.toc.add(text, href, play_order=self.oeb.toc.next_play_order())
                            num += 1
                        except ValueError:
                            self.oeb.log.exception(f'Failed to process link: {href!r}')
                            continue  # Most likely an incorrectly URL encoded link
                        if self.opts.max_toc_links > 0 and num >= self.opts.max_toc_links:
                            self.log('Maximum TOC links reached, stopping.')
                            return

    def elem_to_link(self, item: Manifest.Item, elem: etree._Element, title_attribute: str | None, counter: int) -> tuple[str, str]:
        text = ''
        if title_attribute is not None:
            text = elem.get(title_attribute, '')
        if not text:
            text = xml2text(elem).strip()
        if not text:
            text = elem.get('title', '')
        if not text:
            text = elem.get('alt', '')
        text = re.sub(r'\s+', ' ', text.strip())
        text = text[:1000].strip()
        id = elem.get('id', f'calibre_toc_{counter}')
        elem.set('id', id)
        href = f'{item.href}#{id}'
        return text, href

    def add_leveled_toc_items(self) -> None:
        # Each document is walked once, in document order, tracking the most
        # recently added level 1 and level 2 nodes, which become the parents
        # of subsequent level 2 and level 3 entries. The most recent nodes
        # carry over to later documents. This is linear in the size of the
        # book rather than O(num_headings * document_size).
        counter = 1
        play_order = self.oeb.toc.next_play_order()
        last_level1: TOC | None = None
        last_level2: TOC | None = None

        def find_matches(expr: str, doc: etree._Element) -> list[etree._Element]:
            try:
                ans = XPath(expr)(doc)
                len(ans)
                return ans
            except Exception:
                self.log.warn(f'Invalid ToC expression, ignoring: {expr}')
                return []

        level1_toc, level1_title = self.get_toc_parts_for_xpath(self.opts.level1_toc)
        level2_toc = level2_title = level3_toc = level3_title = None
        if self.opts.level2_toc is not None:
            level2_toc, level2_title = self.get_toc_parts_for_xpath(self.opts.level2_toc)
            if self.opts.level3_toc is not None:
                level3_toc, level3_title = self.get_toc_parts_for_xpath(self.opts.level3_toc)

        for document in self.oeb.spine:
            root = document.data
            assert isinstance(root, etree._Element)  # spine items are always (X)HTML documents
            level1_elems = set(find_matches(level1_toc, root))
            # Lower levels can only be added if there is a possible parent
            level2_elems: set[etree._Element] = set()
            if level2_toc is not None and (last_level1 is not None or level1_elems):
                level2_elems = set(find_matches(level2_toc, root))
            level3_elems: set[etree._Element] = set()
            if level3_toc is not None and (last_level2 is not None or level2_elems):
                level3_elems = set(find_matches(level3_toc, root))
            if not level1_elems and not level2_elems and not level3_elems:
                continue

            for elem in root.iterdescendants(etree.Element):
                if elem in level1_elems:
                    text, _href = self.elem_to_link(document, elem, level1_title, counter)
                    counter += 1
                    if text:
                        last_level1 = self.oeb.toc.add(text, _href, play_order=play_order)
                        play_order += 1
                        # A level 1 entry is never also a level 2 entry, but
                        # can be a level 3 entry
                        level2_elems.discard(elem)
                if elem in level2_elems and last_level1 is not None:
                    text, _href = self.elem_to_link(document, elem, level2_title, counter)
                    counter += 1
                    if text:
                        last_level2 = last_level1.add(text, _href, play_order=play_order)
                        play_order += 1
                        continue  # A level 2 entry is never also a level 3 entry
                if elem in level3_elems and last_level2 is not None:
                    text, _href = self.elem_to_link(document, elem, level3_title, counter)
                    counter += 1
                    if text:
                        last_level2.add(text, _href, play_order=play_order)
                        play_order += 1


def find_tests() -> unittest.TestSuite:
    import unittest
    from optparse import Values

    from calibre.ebooks.oeb.base import XHTML_MIME, OEBBook
    from calibre.utils.logging import default_log

    def make_book(*bodies: str) -> OEBBook:
        oeb = OEBBook(default_log)
        for i, body in enumerate(bodies):
            html = f'<html xmlns="{XHTML_NS}"><head><title>t</title></head><body>{body}</body></html>'
            oeb.spine.add(oeb.manifest.add(f'i{i}', f'd{i}.html', XHTML_MIME, data=html))
        return oeb

    def dump(toc: TOC, level: int = 0) -> list[tuple[int, str, str]]:
        ans = []
        for child in toc:
            ans.append((level, child.title or '', (child.href or '').partition('#')[0]))
            ans.extend(dump(child, level + 1))
        return ans

    class StructureTest(unittest.TestCase):
        def leveled_toc(self, *bodies: str, level3: str | None = '//h:h3') -> list[tuple[int, str, str]]:
            oeb = make_book(*bodies)
            ds = DetectStructure()
            ds.oeb, ds.log = oeb, default_log
            ds.opts = Values({'level1_toc': '//h:h1', 'level2_toc': '//h:h2', 'level3_toc': level3})
            ds.add_leveled_toc_items()
            # play orders are unique and consecutive
            orders = sorted(x.play_order for x in oeb.toc.iterdescendants())
            start = oeb.toc.play_order + 1
            self.assertEqual(orders, list(range(start, start + len(orders))))
            return dump(oeb.toc)

        def test_leveled_toc(self) -> None:
            self.assertEqual(
                self.leveled_toc('<h1>A</h1><h2>B</h2><div><h3>C</h3></div><h1>D</h1><h3>E</h3><h2>F</h2>'),
                [(0, 'A', 'd0.html'), (1, 'B', 'd0.html'), (2, 'C', 'd0.html'), (2, 'E', 'd0.html'), (0, 'D', 'd0.html'), (1, 'F', 'd0.html')],
            )
            # Entries without a parent are dropped, parents carry over across documents
            self.assertEqual(
                self.leveled_toc('<h2>X</h2><h3>Y</h3><h1>A</h1><h2>B</h2><h1>C</h1>', '<h3>D</h3><h2>E</h2>', '<h3>F</h3>'),
                [(0, 'A', 'd0.html'), (1, 'B', 'd0.html'), (2, 'D', 'd1.html'), (0, 'C', 'd0.html'), (1, 'E', 'd1.html'), (2, 'F', 'd2.html')],
            )
            # Entries with no text are ignored and do not become parents
            self.assertEqual(
                self.leveled_toc('<h1>A</h1><h2></h2><h3>B</h3><h2>C</h2><h3>D</h3>'),
                [(0, 'A', 'd0.html'), (1, 'C', 'd0.html'), (2, 'D', 'd0.html')],
            )
            self.assertEqual(
                self.leveled_toc('<h1>A</h1><h2>B</h2><h3>C</h3>', level3=None),
                [(0, 'A', 'd0.html'), (1, 'B', 'd0.html')],
            )

        def test_rationalize_play_orders(self) -> None:
            root = TOC()
            a = root.add('a', 'a.html', play_order=1)
            a.add('b', 'b.html', play_order=2)
            b2 = root.add('b2', 'b.html', play_order=5)
            c = a.add('c', 'c.html', play_order=1)
            d = root.add('d', 'd.html', play_order=2)
            root.rationalize_play_orders()
            self.assertEqual(b2.play_order, 2)
            self.assertNotIn(c.play_order, (0, 1, 2))
            self.assertNotIn(d.play_order, (0, 1, 2, c.play_order))
            seen_po: dict[int, str | None] = {}
            seen_href: dict[str | None, int] = {}
            for x in root.iter():
                self.assertEqual(seen_po.setdefault(x.play_order, x.href), x.href)
                self.assertEqual(seen_href.setdefault(x.href, x.play_order), x.play_order)

    return unittest.defaultTestLoader.loadTestsFromTestCase(StructureTest)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_tests

    run_tests(find_tests)
