#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Tests for splitting a page of a PDF into columns.

poppler reports the position of every fragment of text on the page but says
nothing about the layout, so the columns have to be found from the geometry. A
gutter is a vertical strip of the page that the text does not cross. Looking
for one across the page as a whole, rather than at the gap between two
fragments, is what tells a real gutter apart from the wide spacing of a
justified line, which does not line up from one row to the next.
"""

import os
import random
import re
import unittest
from typing import TYPE_CHECKING

from calibre.ebooks.pdf.reflow import Image, Page, PDFDocument, line_and_para_space
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.icu import logical_to_visual

if TYPE_CHECKING:
    from collections.abc import Sequence

    from calibre.ebooks.conversion.utils import HeuristicProcessor

# (left, top, width, text) or (left, top, width, text, height)
type Fragment = tuple[int, int, int, str] | tuple[int, int, int, str, int]
# (left, top, width, text, font)
type FontFragment = tuple[int, int, int, str, int]


class Opts:
    pdf_header_skip = 0
    pdf_footer_skip = 0
    pdf_header_regex = ''
    pdf_footer_regex = ''
    no_images = True
    verbose = 0
    unwrap_factor = 0.4


def build(fragments: Sequence[Fragment], width: int = 600, height: int = 800, join: bool = True) -> Page:
    """
    Build a Page from (left, top, width, text) or (left, top, width, text,
    height) fragments, the way poppler reports them.
    """
    from calibre.utils.logging import default_log
    from calibre.utils.xml_parse import safe_xml_fromstring

    parts = [f'<page number="1" top="0" left="0" height="{height}" width="{width}">']
    for frag in fragments:
        left, top, w, text = frag[:4]
        h = frag[4] if len(frag) > 4 else 12
        parts.append(f'<text top="{top}" left="{left}" width="{w}" height="{h}">{text}</text>')
    parts.append('</page>')
    opts = Opts()
    page = Page(safe_xml_fromstring(''.join(parts)), {}, opts, default_log, iter(range(100000)))
    if join:
        page.join_fragments(opts)
    return page


# Columns of prose hold a lineful of text, unlike the cells of a table. The
# fixtures below use realistic line lengths so that the check which tells the
# two apart is actually exercised.
LEFT_LINE = 'the left column of this page holds'
RIGHT_LINE = 'the right column of this page holds'


def two_columns(rows: int = 6, left_text: str = LEFT_LINE, right_text: str = RIGHT_LINE) -> list[Fragment]:
    "A plain two column page with a gutter between x=210 and x=250"
    ans: list[Fragment] = []
    for i in range(rows):
        ans.append((10, 10 + i * 20, 200, f'{left_text} {i}'))
        ans.append((250, 10 + i * 20, 200, f'{right_text} {i}'))
    return ans


def texts_of(page: Page) -> list[str]:
    return [t.text_as_string for t in page.texts]


class TestSingleColumn(unittest.TestCase):
    """
    A page that is not in columns must come through exactly as it did before
    columns were looked for at all, as that is the overwhelming majority of
    PDFs.
    """

    def check_not_split(self, fragments: Sequence[Fragment], width: int = 600) -> Page:
        page = build(fragments, width=width)
        self.assertEqual(1, page.column_count)
        for t in page.texts:
            self.assertEqual((0, 0), t.column)
        return page

    def test_plain_page(self) -> None:
        page = self.check_not_split([(10, 10 + i * 20, 400, f'Line {i} of ordinary text') for i in range(8)])
        self.assertEqual(8, len(page.texts))

    def test_fragments_are_still_joined_into_lines(self) -> None:
        page = self.check_not_split([(10, 10, 40, 'The'), (55, 10, 40, 'quick'), (100, 10, 40, 'fox')])
        self.assertEqual(['The quick fox'], texts_of(page))

    def test_empty_page(self) -> None:
        page = build([])
        self.assertEqual(1, page.column_count)
        self.assertEqual([], page.texts)

    def test_too_few_rows_to_tell(self) -> None:
        # Two rows is not enough to know a gap is a gutter and not a wide space
        self.check_not_split([(10, 10, 200, 'Left one'), (330, 10, 200, 'Right one'), (10, 30, 200, 'Left two'), (330, 30, 200, 'Right two')])

    def test_justified_text(self) -> None:
        # Justified text has wide gaps between words, but in a different place
        # on every line, so no strip of the page is free of text
        random.seed(7)
        fragments = []
        for i in range(12):
            x = 10
            for word in range(5):
                fragments.append((x, 10 + i * 20, 70, f'w{word}'))
                x += 70 + random.choice((20, 45, 70, 95))
        self.check_not_split(fragments, width=700)

    def test_block_quote_indent(self) -> None:
        fragments = [(10, 10 + i * 20, 500, f'Ordinary line {i}') for i in range(4)]
        fragments += [(120, 90 + i * 20, 380, f'Indented quotation {i}') for i in range(4)]
        fragments += [(10, 180 + i * 20, 500, f'More ordinary text {i}') for i in range(4)]
        self.check_not_split(fragments)

    def test_centred_title(self) -> None:
        fragments = [(200, 5, 200, 'A Centred Title', 20)]
        fragments += [(10, 40 + i * 20, 550, f'Body line {i}') for i in range(8)]
        self.check_not_split(fragments)

    def test_table_of_contents(self) -> None:
        # The page numbers down the right hand side line up, but they are far
        # too little text to be a column of their own
        fragments = [(10, 10 + i * 20, 300, f'Chapter {i} Of This Book') for i in range(10)]
        fragments += [(560, 10 + i * 20, 20, f'{i * 7}') for i in range(10)]
        self.check_not_split(fragments)

    def test_ragged_right_margin(self) -> None:
        # The right hand margin is empty but it is a margin, not a gutter, as
        # there is no text to the right of it
        self.check_not_split([(10, 10 + i * 20, 200 + (i % 3) * 40, f'Line {i}') for i in range(10)])


class TestColumnDetection(unittest.TestCase):
    def test_two_columns(self) -> None:
        page = build(two_columns())
        self.assertEqual(2, page.column_count)
        self.assertEqual([(0, 0)] * 6 + [(0, 1)] * 6, [t.column for t in page.texts])

    def test_columns_are_read_one_after_the_other(self) -> None:
        page = build(two_columns())
        self.assertEqual([f'{LEFT_LINE} {i}' for i in range(6)] + [f'{RIGHT_LINE} {i}' for i in range(6)], texts_of(page))

    def test_fragments_are_not_joined_across_a_gutter(self) -> None:
        # This is what used to run the two columns of a line together
        page = build(two_columns())
        self.assertEqual(12, len(page.texts))
        for text in texts_of(page):
            self.assertFalse(LEFT_LINE in text and RIGHT_LINE in text, f'The columns were run together: {text!r}')

    def test_fragments_within_a_column_are_still_joined(self) -> None:
        fragments = []
        for i in range(6):
            fragments.append((10, 10 + i * 20, 90, 'the left column of'))
            fragments.append((105, 10 + i * 20, 90, f'this page holds {i}'))
            fragments.append((250, 10 + i * 20, 200, f'{RIGHT_LINE} {i}'))
        page = build(fragments)
        self.assertEqual(2, page.column_count)
        self.assertEqual(
            [f'the left column of this page holds {i}' for i in range(6)] + [f'{RIGHT_LINE} {i}' for i in range(6)],
            texts_of(page),
        )

    def test_three_columns(self) -> None:
        names = ('first', 'second', 'third')
        fragments = []
        for i in range(6):
            for c, x in enumerate((10, 210, 410)):
                fragments.append((x, 10 + i * 20, 180, f'text of the {names[c]} column {i}'))
        page = build(fragments)
        self.assertEqual(3, page.column_count)
        self.assertEqual([f'text of the {n} column {i}' for n in names for i in range(6)], texts_of(page))

    def test_gutters(self) -> None:
        page = build(two_columns(), join=False)
        gutters = page.find_gutters()
        self.assertEqual(1, len(gutters))
        start, end = gutters[0]
        self.assertTrue(210 <= start < end <= 250, f'Unexpected gutter: {gutters[0]}')

    def test_paragraphs_are_not_merged_across_a_gutter(self) -> None:
        # The last line of one column and the first of the next line up
        # vertically in a way that used to look like a paragraph continuing
        page = build(two_columns())
        left_last = [t for t in page.texts if t.column == (0, 0)][-1]
        right_first = [t for t in page.texts if t.column == (0, 1)][0]
        self.assertNotEqual(left_last.column, right_first.column)


class TestSpanningElements(unittest.TestCase):
    """
    An element that crosses a gutter, such as a heading over a two column
    body, belongs to neither column. It starts a new band of the page and is
    read before the columns below it.
    """

    def test_heading_over_two_columns(self) -> None:
        fragments = [(10, 5, 440, 'A Full Width Heading Over The Page', 20)] + [
            (x, 45 + i * 20, 200, f'{name} {i}') for i in range(6) for x, name in ((10, LEFT_LINE), (250, RIGHT_LINE))
        ]
        page = build(fragments)
        self.assertEqual(2, page.column_count)
        self.assertEqual('A Full Width Heading Over The Page', texts_of(page)[0])
        self.assertEqual([f'{LEFT_LINE} {i}' for i in range(6)] + [f'{RIGHT_LINE} {i}' for i in range(6)], texts_of(page)[1:])

    def test_heading_over_a_short_page(self) -> None:
        # Few enough rows that the allowance for rows crossing a gutter rounds
        # down to none, so the heading would otherwise hide the gutter
        fragments = [(10, 5, 440, 'A Full Width Heading Over The Page', 20)] + [
            (x, 45 + i * 20, 200, f'{name} {i}') for i in range(4) for x, name in ((10, LEFT_LINE), (250, RIGHT_LINE))
        ]
        page = build(fragments)
        self.assertEqual(2, page.column_count)
        self.assertEqual('A Full Width Heading Over The Page', texts_of(page)[0])

    def test_heading_in_the_middle_starts_a_new_band(self) -> None:
        fragments = []
        for i in range(4):
            fragments.append((10, 10 + i * 20, 200, f'{LEFT_LINE} {i}'))
            fragments.append((250, 10 + i * 20, 200, f'{RIGHT_LINE} {i}'))
        fragments.append((10, 100, 440, 'A Mid Page Heading Over The Page', 18))
        for i in range(4, 8):
            fragments.append((10, 50 + i * 20, 200, f'{LEFT_LINE} {i}'))
            fragments.append((250, 50 + i * 20, 200, f'{RIGHT_LINE} {i}'))
        page = build(fragments)
        self.assertEqual(
            [f'{LEFT_LINE} {i}' for i in range(4)]
            + [f'{RIGHT_LINE} {i}' for i in range(4)]
            + ['A Mid Page Heading Over The Page']
            + [f'{LEFT_LINE} {i}' for i in range(4, 8)]
            + [f'{RIGHT_LINE} {i}' for i in range(4, 8)],
            texts_of(page),
        )

    def test_a_spanning_element_is_not_joined_to_a_column(self) -> None:
        # The heading sits above the body, it does not overlap the first row
        fragments = [(10, 5, 440, 'A Full Width Heading Over The Page', 20)] + [
            (x, 45 + i * 20, 200, f'{name} {i}') for i in range(6) for x, name in ((10, LEFT_LINE), (250, RIGHT_LINE))
        ]
        page = build(fragments)
        self.assertIn('A Full Width Heading Over The Page', texts_of(page))
        for text in texts_of(page):
            if 'Heading' in text:
                self.assertEqual('A Full Width Heading Over The Page', text)


class TestTables(unittest.TestCase):
    """
    The cells of a table line up into neat vertical strips just as columns of
    prose do, but a table has to be read one row at a time. Reading it a
    column at a time would scatter each row across the page, so a page whose
    strips hold too little text to be prose is left alone.
    """

    def table(self, rows: int = 12) -> list[Fragment]:
        ans: list[Fragment] = []
        for i in range(rows):
            ans.append((10, 10 + i * 20, 80, f'Item {i}'))
            ans.append((230, 10 + i * 20, 60, f'{i * 11}'))
            ans.append((430, 10 + i * 20, 60, f'{i * 37}'))
        return ans

    def test_a_table_is_not_split_into_columns(self) -> None:
        page = build(self.table())
        self.assertEqual(1, page.column_count)

    def test_the_rows_of_a_table_stay_together(self) -> None:
        page = build(self.table())
        self.assertEqual(12, len(page.texts))
        for i, text in enumerate(texts_of(page)):
            self.assertIn(f'Item {i}', text)
            self.assertIn(str(i * 11), text)
            self.assertIn(str(i * 37), text)

    def test_a_two_column_list_of_short_entries_is_left_alone(self) -> None:
        # Conservative: without a lineful of text on each row there is no way
        # to tell a two column list from a table, so it is not split
        fragments = []
        for i in range(10):
            fragments.append((10, 10 + i * 20, 80, f'Apples {i}'))
            fragments.append((330, 10 + i * 20, 80, f'Pears {i}'))
        self.assertEqual(1, build(fragments).column_count)


class TestRightToLeftColumns(unittest.TestCase):
    "On a right-to-left page the rightmost column is read first"

    # Hebrew for "the left/right column of the page", long enough to be prose
    RTL_LEFT = 'הטור השמאלי של העמוד הזה מכיל'
    RTL_RIGHT = 'הטור הימני של העמוד הזה מכיל'

    def rtl_two_columns(self, rows: int = 6) -> list[Fragment]:
        ans: list[Fragment] = []
        for i in range(rows):
            ans.append((10, 10 + i * 20, 200, logical_to_visual(f'{self.RTL_LEFT} {i}')))
            ans.append((250, 10 + i * 20, 200, logical_to_visual(f'{self.RTL_RIGHT} {i}')))
        return ans

    def page(self, fragments: Sequence[Fragment]) -> Page:
        page = build(fragments)
        for t in page.texts:
            t.convert_visual_order_to_logical()
        return page

    def test_right_column_is_read_first(self) -> None:
        page = self.page(self.rtl_two_columns())
        self.assertEqual(2, page.column_count)
        self.assertEqual(
            [f'{self.RTL_RIGHT} {i}' for i in range(6)] + [f'{self.RTL_LEFT} {i}' for i in range(6)],
            texts_of(page),
        )

    def test_columns_are_not_mirrored_into_each_other(self) -> None:
        # Each column is reordered on its own, so no word of one column can
        # end up in the other
        page = self.page(self.rtl_two_columns())
        for t in page.texts:
            self.assertFalse(
                'הימני' in t.text_as_string and 'השמאלי' in t.text_as_string,
                f'The columns were run together: {t.text_as_string!r}',
            )

    def test_left_to_right_page_keeps_left_column_first(self) -> None:
        page = self.page(two_columns())
        self.assertEqual(f'{LEFT_LINE} 0', texts_of(page)[0])

    def test_mostly_english_page_with_some_hebrew_is_left_to_right(self) -> None:
        fragments = two_columns()
        fragments.append((250, 130, 200, logical_to_visual('שלום')))
        page = self.page(fragments)
        self.assertEqual(f'{LEFT_LINE} 0', texts_of(page)[0])


class TestPageBoundaries(unittest.TestCase):
    """
    Pages are joined together into a single flow of text, with page numbers
    removed and paragraphs that continue onto the next page merged.
    """

    BODY = 'Some ordinary text that fills up most of the width of a line'

    def convert(self, pages: Sequence[Sequence[FontFragment]]) -> str:
        """
        Convert a document whose pages are lists of (left, top, width, text,
        font) fragments, returning the generated HTML.
        """
        from calibre.utils.logging import default_log

        parts = ['<pdf2xml>']
        for num, fragments in enumerate(pages, start=1):
            parts.append(f'<page number="{num}" top="0" left="0" height="1349" width="1800">')
            if num == 1:
                parts.append('<fontspec id="0" size="24" family="Body" color="#000000"/>')
                parts.append('<fontspec id="1" size="31" family="Heading" color="#000000"/>')
                parts.append('<fontspec id="2" size="21" family="Caption" color="#000000"/>')
                parts.append('<fontspec id="3" size="24" family="CourierNew" color="#000000"/>')
                parts.append('<fontspec id="4" size="24" family="ABCDEF+NimbusMonL-Regu" color="#000000"/>')
            for left, top, width, text, font in fragments:
                parts.append(f'<text top="{top}" left="{left}" width="{width}" height="29" font="{font}">{text}</text>')
            parts.append('</page>')
        parts.append('</pdf2xml>')
        opts = Opts()
        opts.pdf_header_skip = opts.pdf_footer_skip = -1
        with TemporaryDirectory() as tdir:
            cwd = os.getcwd()
            os.chdir(tdir)
            try:
                PDFDocument(''.join(parts).encode('utf-8'), opts, default_log)
                with open('index.html', encoding='utf-8') as f:
                    return f.read()
            finally:
                os.chdir(cwd)

    def text_page(self, num: int, heading: str = '', page_number: bool = True) -> list[FontFragment]:
        # Vary the text so that it is not mistaken for a header or footer
        words = 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu'.split()
        ans: list[FontFragment] = [(337, 132, 800, heading, 1)] if heading else []
        ans += [(337, 223 + i * 35, 1100, f'{self.BODY} {words[num % len(words)]} {words[i]}.', 0) for i in range(12)]
        if page_number:
            ans.append((892, 1212, 15 * len(str(num)), str(num), 0))
        return ans

    def test_bare_page_numbers_are_removed(self) -> None:
        html = self.convert([self.text_page(i + 2) for i in range(6)])
        self.assertIn(f'{self.BODY} gamma alpha.', html)
        for i in range(6):
            self.assertNotIn(f'>{i + 2}<', html)

    def book_pages(self, count: int) -> list[list[FontFragment]]:
        """
        Pages laid out as a printed book, with one paragraph flowing across
        all of them, and running heads with the page number and the book or
        chapter title, except on the first page, which starts a chapter and
        has the page number at the bottom
        """
        pages: list[list[FontFragment]] = []
        for num in range(1, count + 1):
            page: list[FontFragment] = []
            if num == 1:
                page.append((337, 132, 600, 'CHAPTER I. The Beginning', 1))
                page.append((892, 1212, 15, '1', 0))
            elif num % 2 == 0:
                page += [(337, 100, 15 * len(str(num)), str(num), 0), (1300, 100, 137, 'THE BOOK', 0)]
            else:
                page += [(337, 100, 300, 'CHAPTER I. THE BEGINNING', 0), (1437 - 15 * len(str(num)), 100, 15 * len(str(num)), str(num), 0)]
            words = 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega'.split()
            for i in range(24):
                left = 380 if num == 1 and i == 0 else 337
                page.append((left, 223 + i * 40, 1437 - left, f'{self.BODY} {words[num]} {words[i]} and then', 0))
            pages.append(page)
        return pages

    def test_running_heads_with_titles_are_removed(self) -> None:
        html = self.convert(self.book_pages(8))
        self.assertNotIn('THE BOOK', html)
        self.assertNotIn('THE BEGINNING', html)
        self.assertIn('The Beginning', html)
        for num in range(1, 9):
            self.assertNotRegex(html, rf'>\s*{num}\s*<')
        paras = [p for p in self.paragraph_texts(html) if self.BODY in p]
        self.assertEqual(1, len(paras), paras)
        self.assertEqual(8 * 24, paras[0].count(self.BODY))

    def test_section_numbers_at_top_of_page_are_not_page_numbers(self) -> None:
        # Numbered section headings at the top of the body of some pages,
        # whose numbers happen to differ from the page number by the same
        # amount, are not running heads
        words = 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda'.split()
        pages: list[list[FontFragment]] = []
        for num in range(1, 11):
            page: list[FontFragment] = []
            top = 223
            if num in (3, 5, 7, 9):
                page.append((337, top, 400, f'{num - 1} Section {words[num]}', 1))
                top += 60
            while top < 1100:
                page.append((337, top, 1100, f'{self.BODY} {words[num]} {top} and', 0))
                top += 40
            pages.append(page)
        html = self.convert(pages)
        for num in (3, 5, 7, 9):
            self.assertIn(f'{num - 1} Section {words[num]}', html)

    def test_numbers_in_text_are_not_page_numbers(self) -> None:
        # The last line of each page ends with a number, but not the page number
        pages = self.book_pages(6)
        words = 'apples pears plums cherries grapes lemons'.split()
        for num, page in enumerate(pages, start=1):
            page.append((337, 223 + 24 * 40, 600, f'and the {words[num - 1]} numbered {num * 7 + 3}', 0))
        html = self.convert(pages)
        for num in range(1, 7):
            self.assertIn(f'numbered {num * 7 + 3}', html)

    def test_paragraph_continues_after_sentence_at_end_of_page(self) -> None:
        # The last line of a page is the indented first line of a paragraph,
        # ending a sentence. The paragraph continues on the next page, whose
        # first line is not indented, so it is not a new paragraph.
        first = [(337, 223 + i * 35, 1100, f'{self.BODY} alpha {i} and', 0) for i in range(11)]
        first[-1] = (337, first[-1][1], 1100, f'{self.BODY} alpha 10.', 0)
        first.append((380, 223 + 11 * 35, 1057, 'Then a new paragraph begins here, and it is a long one.', 0))
        # The first word of the next page would fit in the indent, but it
        # does not fit at the end of the line, as it is full
        second = [(337, 223 + i * 35, 1100, f'I continue the paragraph {self.BODY} beta {i} and', 0) for i in range(12)]
        paras = self.paragraph_texts(self.convert([first, second]))
        matching = [p for p in paras if 'Then a new paragraph' in p]
        self.assertEqual(1, len(matching), paras)
        self.assertIn('I continue the paragraph', matching[0])

    def test_wide_space_after_sentence_in_justified_line(self) -> None:
        # Justification can widen the space after the end of a sentence so
        # much that the rest of the line is a separate fragment, ending at
        # the right margin. That is not text aligned to the right, such as a
        # page number in a table of contents, so the line is still joined to
        # the next one.
        page = [(337, 223 + i * 35, 1100, f'{self.BODY} line {i} and', 0) for i in range(4)]
        page += [(380, 363, 30, 'Mr.', 0), (450, 363, 987, f'Smith said {self.BODY} which', 0)]
        page += [(337, 398 + i * 35, 1100, f'continues {self.BODY} more {i} and', 0) for i in range(4)]
        page[-1] = (337, page[-1][1], 600, 'and ends here.', 0)
        paras = self.paragraph_texts(self.convert([page]))
        matching = [p for p in paras if 'Mr.' in p]
        self.assertEqual(1, len(matching), paras)
        self.assertIn('continues', matching[0])
        self.assertIn('ends here.', matching[0])

    def test_code_with_comments_at_right_is_not_joined(self) -> None:
        # Lines of code ending a statement, followed by a comment at the right
        page = self.body_lines(223, 4)
        for i in range(6):
            top = 400 + i * 35
            page += [(337, top, 500, f'profile_t *profile_number_{i};', 0), (1000, top, 430, f'/* The profile for device {i} */', 2)]
        page += self.body_lines(650, 4)
        paras = [p for p in self.paragraph_texts(self.convert([page])) if 'profile_number' in p]
        self.assertEqual(6, len(paras), paras)

    def test_contents_with_lettered_page_numbers(self) -> None:
        page: list[FontFragment] = []
        for i in range(8):
            top = 223 + i * 35
            page += [(337, top, 1000, f'Appendix part {i + 1} . . . . . . . . . . . . . .', 0), (1397, top, 40, f'A-{i + 1}', 0)]
        paras = [p for p in self.paragraph_texts(self.convert([page])) if 'Appendix part' in p]
        self.assertEqual(8, len(paras), paras)

    def test_paragraph_indent_with_more_common_code_indent(self) -> None:
        # Code, indented a little less than the first lines of paragraphs, is
        # more common than those first lines, but is not the paragraph indent
        page: list[FontFragment] = []
        top = 150
        for p in range(6):
            page.append((390, top, 1047, f'Paragraph{p} line 0 {self.BODY}', 0))
            top += 35
            for i in range(1, 3):
                page.append((337, top, 1100, f'Paragraph{p} line {i} {self.BODY}', 0))
                top += 35
            for i in range(2):
                page.append((380, top, 300, f'(code {p} {i})', 0))
                top += 35
        paras = self.paragraph_texts(self.convert([page]))
        for p in range(6):
            matching = [x for x in paras if f'Paragraph{p} ' in x]
            self.assertEqual(1, len(matching), paras)
            self.assertEqual(3, matching[0].count(self.BODY), matching[0])

    def list_items(self, top: int, labels: Sequence[str], lines: int = 3) -> list[FontFragment]:
        # Items with a label, and their text and following lines further right
        page: list[FontFragment] = []
        for n, label in enumerate(labels):
            page.append((360, top, 30, label, 0))
            for i in range(lines):
                page.append((410, top, 1027 if i < lines - 1 else 500, f'Item{n} line {i} {self.BODY}', 0))
                top += 35
            top += 10
        return page

    def test_list_items_with_hanging_indent(self) -> None:
        for labels in (['•', '•', '•'], ['1.', '2.', '3.'], ['9.1.', '9.2.', '9.3.']):
            with self.subTest(labels=labels):
                page = self.body_lines(150, 4) + self.list_items(320, labels) + self.body_lines(700, 4, label='after ')
                paras = self.paragraph_texts(self.convert([page]))
                for n in range(3):
                    matching = [x for x in paras if f'Item{n} ' in x]
                    self.assertEqual(1, len(matching), paras)
                    self.assertEqual(3, matching[0].count(self.BODY), matching[0])
                    self.assertEqual({f'Item{n}'}, set(re.findall(r'Item\d', matching[0])), matching[0])
                    self.assertNotIn('after', matching[0])

    def test_list_item_continues_on_next_page(self) -> None:
        first = self.body_lines(223, 26)
        first += [(360, 1180, 30, '•', 0), (410, 1180, 1027, f'Item0 line 0 {self.BODY}', 0)]
        second = [(410, 223, 600, 'and the item ends here.', 0)] + self.body_lines(300, 20, label='after ')
        paras = self.paragraph_texts(self.convert([first, second]))
        matching = [x for x in paras if 'Item0' in x]
        self.assertEqual(1, len(matching), paras)
        self.assertIn('the item ends here.', matching[0])
        self.assertNotIn('after', matching[0])

    def test_list_items_are_not_centered_or_right_aligned(self) -> None:
        # The first line of an item has about the same space to its left and
        # right, and its last line is at its hanging indent, far from the
        # left, but the items as a whole are neither centered nor right aligned
        for lines in (2, 3):
            with self.subTest(lines=lines):
                page = self.body_lines(150, 4)
                top = 320
                for n in range(3):
                    page += [(355, top, 20, '•', 0), (390, top, 1047, f'Item{n} line 0 {self.BODY}', 0)]
                    for i in range(1, lines):
                        page.append((390, top + i * 35, 1047 if i < lines - 1 else 300, f'Item{n} line {i} ends.', 0))
                    top += lines * 35 + 10
                page += self.body_lines(top + 50, 4, label='after ')
                for line in self.convert([page]).splitlines():
                    if 'Item' in line:
                        self.assertNotIn('text-align', line)

    def test_alignment_of_two_line_items_is_of_the_whole_item(self) -> None:
        # Deeply indented items of two lines, whose last lines alone would
        # look centered or right aligned
        for last_width in (400, 300):
            with self.subTest(last_width=last_width):
                page = self.body_lines(150, 4)
                page += [(660, 320, 20, '•', 0), (700, 320, 737, f'Item line 0 {self.BODY}', 0), (700, 355, last_width, 'Item ends.', 0)]
                page += self.body_lines(450, 4, label='after ')
                for line in self.convert([page]).splitlines():
                    if 'Item' in line:
                        self.assertNotIn('text-align', line)

    def test_long_lines_at_common_left_are_not_centered(self) -> None:
        # Lines that start where many other lines do, such as examples in a
        # book, are aligned there, even if they look centered on their own
        pages = []
        for num in range(4):
            page: list[FontFragment] = []
            top = 150
            for i in range(6):
                page += [(337, top + 35 * j, 1100, f'{self.BODY} {num} {i} {j} and', 0) for j in range(3)]
                page.append((600, top + 105, 600, f'Example {num} {i} goes here.', 0))
                top += 175
            pages.append(page)
        for line in self.convert(pages).splitlines():
            if 'Example' in line:
                self.assertNotIn('center', line)

    def test_paragraph_after_list_item_at_indent(self) -> None:
        # The text of list items starts at the indent of paragraphs, so the
        # first line of the paragraph after the list is at the hanging indent
        # of the last item
        page = [(380, 150 + i * 120, 1057, f'Para{i} {self.BODY}', 0) for i in range(3)]
        for i in range(3):
            page += [(337, 185 + i * 120 + j * 35, 1100, f'{self.BODY} more {i} {j}', 0) for j in range(2)]
        page += [(337, 520, 20, '•', 0), (380, 520, 1057, f'The only item {self.BODY} ends.', 0)]
        page += [(380, 555, 1057, f'Next paragraph {self.BODY} goes', 0), (337, 590, 1100, f'on {self.BODY} here', 0)]
        paras = self.paragraph_texts(self.convert([page]))
        item = [p for p in paras if 'The only item' in p]
        self.assertEqual(1, len(item), paras)
        self.assertNotIn('Next paragraph', item[0])
        nxt = [p for p in paras if 'Next paragraph' in p]
        self.assertEqual(1, len(nxt), paras)
        self.assertIn('here', nxt[0])

    def test_block_of_text_at_paragraph_indent(self) -> None:
        # Such as the definitions in a glossary, whose lines all start at the
        # indent of paragraphs
        page: list[FontFragment] = []
        top = 150
        for p in range(6):
            page.append((380, top, 1057, f'Paragraph{p} line 0 {self.BODY}', 0))
            page += [(337, top + 35 * (i + 1), 1100, f'Paragraph{p} line {i + 1} {self.BODY}', 0) for i in range(2)]
            top += 115
        page.append((337, top, 300, 'glossary term', 0))
        page += [(380, top + 35 * (i + 1), 1057 if i < 2 else 400, f'Definition line {i} {self.BODY}', 0) for i in range(3)]
        paras = self.paragraph_texts(self.convert([page]))
        definition = [p for p in paras if 'Definition line' in p]
        self.assertEqual(1, len(definition), paras)
        self.assertEqual(3, definition[0].count(self.BODY))

    def test_code_lines_are_not_joined_or_centered(self) -> None:
        # Lines of code, further right than the indent of paragraphs
        page: list[FontFragment] = []
        for p in range(6):
            top = 150 + p * 105 + (300 if p > 2 else 0)
            page += [(380, top, 1057, f'Paragraph{p} {self.BODY}', 0)] + [(337, top + 35 * (i + 1), 1100, f'{self.BODY} {p} {i}', 0) for i in range(2)]
        page += [(420, 470 + i * 35, 950, f'(defun function-number-{i} (x) (list x x x x {i}))', 3) for i in range(6)]
        lines = [line for line in self.convert([page]).splitlines() if 'function-number' in line]
        self.assertEqual(6, len(lines), lines)
        for line in lines:
            self.assertNotIn('center', line)

    def test_contents_entries_beyond_paragraph_indent(self) -> None:
        # Entries of a table of contents further right than the first lines
        # of paragraphs elsewhere, which continue at the left margin, are not
        # an indented block of text
        pages = []
        for num in range(3):
            page: list[FontFragment] = []
            top = 150
            for p in range(5):
                page.append((380, top, 1057, f'First line of paragraph {p} on page {num} {self.BODY}', 0))
                page += [(337, top + 35 * (i + 1), 1100, f'{self.BODY} continued', 0) for i in range(3)]
                top += 160
            pages.append(page)
        toc = [(420, 223 + i * 35, 1017, f'Section {i + 1} . . . . . . . . . . . . . . . . {i + 3}', 0) for i in range(10)]
        paras = [p for p in self.paragraph_texts(self.convert([toc] + pages)) if 'Section' in p]
        self.assertEqual(10, len(paras), paras)

    def heading_page(self, heading: Sequence[tuple[int, int, str]]) -> str:
        # A page with a heading of the given (left, width, text) lines in a
        # larger font than the body, wrapped onto more lines
        page: list[FontFragment] = [(left, 132 + i * 45, width, text, 1) for i, (left, width, text) in enumerate(heading)]
        page += self.body_lines(132 + len(heading) * 45 + 60, 16)
        return self.convert([page])

    def headings(self, html: str) -> list[str]:
        from calibre.utils.xml_parse import safe_xml_fromstring

        return [re.sub(r'\s+', ' ', ''.join(h.itertext())).strip() for h in safe_xml_fromstring(html).xpath('//*[local-name()="h2"]')]

    def test_wrapped_heading_is_one_heading(self) -> None:
        html = self.heading_page([(337, 900, 'Chapter 2. The Very Long and'), (337, 600, 'Winding Title')])
        self.assertEqual(['Chapter 2. The Very Long and Winding Title'], self.headings(html))
        # Centered on the page
        html = self.heading_page([(400, 1000, 'Chapter 2. The Very Long and'), (420, 960, 'Winding Title Is Here'), (800, 200, 'Again')])
        self.assertEqual(['Chapter 2. The Very Long and Winding Title Is Here Again'], self.headings(html))

    def test_heading_lines_that_are_not_wrapped(self) -> None:
        # A short line followed by one whose first word would have fitted on
        # it is set on separate lines on purpose
        from calibre.utils.xml_parse import safe_xml_fromstring

        def blocks(html: str) -> list[str]:
            return [re.sub(r'\s+', ' ', ''.join(b.itertext())).strip() for b in safe_xml_fromstring(html).xpath('//*[local-name()="p" or local-name()="h2"]')]

        html = self.heading_page([(337, 300, 'Chapter 2.'), (337, 400, 'The Title')])
        self.assertIn('Chapter 2.', blocks(html))
        self.assertIn('The Title', blocks(html))
        # The first word of the next line would just fit
        html = self.heading_page([(337, 900, 'Chapter 2. The Very Long and'), (337, 100, 'Win')])
        self.assertIn('Win', blocks(html))

    def test_title_page_with_subtitle(self) -> None:
        # A page with nothing but a title and subtitle, so that the title is
        # the widest text on it, but the subtitle would have fitted after it
        from calibre.utils.xml_parse import safe_xml_fromstring

        pages = [[(500, 300, 700, 'The Manual of Things', 1), (600, 345, 500, 'Version 1.2 Beta', 1)]]
        pages += [self.body_lines(223, 28) for i in range(3)]
        html = self.convert(pages)
        blocks = [re.sub(r'\s+', ' ', ''.join(b.itertext())).strip() for b in safe_xml_fromstring(html).xpath('//*[local-name()="p" or local-name()="h2"]')]
        self.assertIn('Version 1.2 Beta', blocks)

    def test_large_text_that_is_not_wrapped(self) -> None:
        # Contents entries and rows of a table in a large font, reaching the
        # right of the text, are not wrapped headings
        contents: list[FontFragment] = []
        table: list[FontFragment] = []
        for i in range(6):
            top = 150 + i * 45
            contents += [(337, top, 600, f'Chapter {i + 1} The Title of Chapter', 1), (1397, top, 40, str(10 * i + 5), 1)]
            table += [(337, top, 300, f'Cell {i} first', 1), (737, top, 300, f'Cell {i} second', 1), (1137, top, 300, f'Cell {i} third', 1)]
        from calibre.utils.xml_parse import safe_xml_fromstring

        for page in (contents, table):
            html = self.convert([page + self.body_lines(450, 20)])
            blocks = [''.join(b.itertext()) for b in safe_xml_fromstring(html).xpath('//*[local-name()="p" or local-name()="h2"]')]
            matching = [b for b in blocks if 'Chapter' in b or 'Cell' in b]
            self.assertEqual(6, len(matching), matching)

    def test_code_in_nimbus_mono_is_not_joined(self) -> None:
        page: list[FontFragment] = []
        for p in range(6):
            top = 150 + p * 105 + (300 if p > 2 else 0)
            page += [(380, top, 1057, f'Paragraph{p} {self.BODY}', 0)] + [(337, top + 35 * (i + 1), 1100, f'{self.BODY} {p} {i}', 0) for i in range(2)]
        page += [(420, 470 + i * 35, 950, f'(defun function-number-{i} (x) (list x x x x {i}))', 4) for i in range(6)]
        lines = [line for line in self.convert([page]).splitlines() if 'function-number' in line]
        self.assertEqual(6, len(lines), lines)

    def test_contents_page_numbers_are_not_joined(self) -> None:
        # Entries ending with a page number at the right margin are separate
        page: list[FontFragment] = []
        for i in range(8):
            top = 223 + i * 35
            page += [(337, top, 700, f'Chapter {i + 1}. The title of chapter number {i + 1} of the book.', 0), (1407, top, 30, str(10 * i + 5), 0)]
        paras = [p for p in self.paragraph_texts(self.convert([page])) if 'chapter number' in p]
        self.assertEqual(8, len(paras), paras)
        for i, p in enumerate(paras):
            self.assertIn(f'chapter number {i + 1} ', p)

    def test_chapter_in_prose_is_not_a_heading(self) -> None:
        sentence = 'chapter before proceeding to the next set of examples and exercises'
        page = [(337, 223 + i * 35, 700, f'{self.BODY} line {i}.', 0) for i in range(12)]
        page[3] = (337, 328, 1100, sentence, 0)
        html = self.convert([page])
        self.assertIn(sentence, html)
        self.assertNotRegex(html, r'<h[1-6][^>]*>chapter before proceeding')

    def test_chapter_prefixed_prose_at_page_start(self) -> None:
        first = self.text_page(0, page_number=False)
        first.append((337, 1178, 1100, 'The explanation continues in this', 0))
        for separate in (False, True):
            with self.subTest(followed_by_paragraph_gap=separate):
                second = self.text_page(1, page_number=False)
                second[0] = (337, 223, 1100, 'Chapter before proceeding to another example.', 0)
                if separate:
                    second[1:] = [(337, 315 + i * 35, 1100, f'{self.BODY} later {i}.', 0) for i in range(6)]
                html = self.convert([first, second])
                self.assertNotRegex(html, r'<h[1-6][^>]*>Chapter before proceeding')
                self.assertIn('Chapter before proceeding to another example.', html)

    def test_chapter_titles_keep_heading_markup(self) -> None:
        for top, font, left, width in (
            (132, 0, 337, 800),
            (258, 1, 337, 800),
            (258, 0, 700, 400),
            (500, 0, 337, 800),
        ):
            with self.subTest(top=top, font=font, left=left):
                before = [] if top == 132 else [(337, 223, 700, f'{self.BODY} before.', 0)]
                after = [(337, max(600, top + 100) + i * 35, 700, f'{self.BODY} after {i}.', 0) for i in range(6)]
                html = self.convert([before + [(left, top, width, 'Chapter One', font)] + after])
                self.assertRegex(html, r'<h2[^>]*>.*Chapter One')

    def test_left_aligned_body_font_titles_are_headings(self) -> None:
        # Titles set in the body font, left aligned, at the top of a page and
        # followed by an ordinary line gap
        for title in ('Chapter 1: The Beginning', 'Chapter 12.', 'Chapter Twenty One', 'CHAPTER IV. The Storm', 'Prologue', 'Epilogue: Years Later'):
            with self.subTest(title=title):
                page = [(337, 223, 500, title, 0)] + [(337, 258 + i * 35, 1100, f'{self.BODY} {i}.', 0) for i in range(8)]
                html = self.convert([page])
                self.assertRegex(html, rf'<h2[^>]*>[^\n]*{re.escape(title)}')

    def test_prose_starting_with_heading_words_is_not_a_heading(self) -> None:
        for text in (
            'Chapter 3 discusses the theory in rather more depth than this one does',
            'Prologue writers in the early modern period were mostly anonymous figures',
            'Epilogues were spoken by a single actor after the end of the main play',
            'The ending of this play is commonly known as the epilogue',
        ):
            with self.subTest(text=text):
                page = [(337, 223 + i * 35, 1100, f'{self.BODY} {i}.', 0) for i in range(4)]
                page.append((380, 223 + 4 * 35, 1100, text, 0))
                page += [(337, 223 + (5 + i) * 35, 1100, f'{self.BODY} {5 + i}.', 0) for i in range(4)]
                html = self.convert([page])
                self.assertIn(text, html)
                self.assertNotRegex(html, r'<h[1-6][^>]*>[^<]*(Chapter|Prologue|Epilogue|The ending)')

    def test_short_lowercase_continuation_at_page_start(self) -> None:
        # The short last line of a sentence continued from the previous page
        first = self.text_page(0, page_number=False)
        first.append((337, 1178, 1100, 'The explanation is the same as the one given in this', 0))
        second = [(337, 223, 300, 'chapter two.', 0)]
        second += [(380, 258 + i * 35, 1100, f'{self.BODY} later {i}.', 0) for i in range(8)]
        html = self.convert([first, second])
        self.assertIn('chapter two.', html)
        self.assertNotRegex(html, r'<h[1-6][^>]*>[^<]*chapter two')

    def body_lines(self, top: int, count: int, step: int = 35, left: int = 337, width: int = 1100, label: str = '') -> list[FontFragment]:
        return [(left, top + i * step, width, f'{self.BODY} {label}{i}.', 0) for i in range(count)]

    def assert_heading(self, html: str, text: str) -> None:
        self.assertRegex(html, rf'<h2[^>]*>[^\n]*{re.escape(text)}')

    def assert_not_heading(self, html: str, text: str) -> None:
        self.assertIn(text, html)
        self.assertNotRegex(html, rf'<h[1-6][^>]*>[^\n]*{re.escape(text)}')

    def test_title_split_into_fragments_is_a_heading(self) -> None:
        # Such as a bold "Chapter 1:" followed by the title in a regular font
        page = [(337, 223, 160, 'Chapter 1:', 0), (505, 223, 330, 'The Beginning', 0)] + self.body_lines(300, 8)
        self.assert_heading(self.convert([page]), 'The Beginning')

    def test_wrapped_title_at_page_start_is_a_heading(self) -> None:
        page = [
            (337, 223, 1100, 'Chapter 1: In Which Our Hero Sets Out Upon A Very Long Journey', 0),
            (337, 258, 300, 'Across The Sea', 0),
        ] + self.body_lines(340, 8)
        html = self.convert([page])
        self.assert_heading(html, 'Chapter 1: In Which Our Hero')
        self.assertIn('Across The Sea', html)

    def test_cross_reference_continued_from_previous_page(self) -> None:
        first = self.text_page(0, page_number=False)
        first.append((337, 1178, 1100, 'The reasons for this are explained in great detail in', 0))
        second = [(337, 223, 150, 'Chapter 3.', 0)] + self.body_lines(258, 8, left=380, label='later ')
        self.assert_not_heading(self.convert([first, second]), 'Chapter 3.')

    def test_paragraph_after_a_gap_is_not_a_heading(self) -> None:
        para = [(337, 400 + i * 35, 1100, f'Chapter 5 covers this in depth, in many words {i}', 0) for i in range(5)]
        page = self.body_lines(223, 3) + para + self.body_lines(400 + 5 * 35, 4, label='after ')
        self.assert_not_heading(self.convert([page]), 'Chapter 5 covers')

    def test_larger_word_does_not_make_a_paragraph_a_heading(self) -> None:
        page = (
            self.body_lines(223, 3)
            + [
                (380, 328, 400, 'Chapter 5 covers the', 0),
                (790, 328, 150, 'LARGE', 1),
                (950, 328, 487, 'word in a paragraph,', 0),
            ]
            + self.body_lines(363, 4, label='after ')
        )
        self.assert_not_heading(self.convert([page]), 'Chapter 5 covers')

    def test_double_spaced_paragraph_is_not_a_heading(self) -> None:
        page = (
            self.body_lines(223, 3, step=70)
            + [
                (380, 433, 1057, 'Chapter 3 discusses the theory in rather more depth than this one', 0),
                (337, 503, 200, 'does here.', 0),
            ]
            + self.body_lines(573, 4, step=70, left=380, label='after ')
        )
        self.assert_not_heading(self.convert([page]), 'Chapter 3 discusses')

    def test_line_in_a_column_is_not_a_heading(self) -> None:
        page: list[FontFragment] = []
        for i in range(12):
            left_text = 'Chapter 3 discusses the theory in more' if i == 5 else f'The left column has some text {i:02d} in it'
            page.append((100, 223 + i * 35, 700, left_text, 0))
            page.append((1000, 223 + i * 35, 700, f'The right column has some text {i:02d} in it', 0))
        self.assert_not_heading(self.convert([page]), 'Chapter 3 discusses')

    def test_caption_is_not_merged_with_next_page(self) -> None:
        # A centred image caption at the bottom of one page followed by a
        # heading at the top of the next must remain separate paragraphs, even
        # though the caption ends with whitespace
        pages = [self.text_page(i, page_number=False) for i in range(6)]
        pages[2] = [(659, 1045, 480, 'Caption of the image, 2026. ', 2)]
        pages[3] = self.text_page(3, heading='The heading after the caption', page_number=False)
        paras = [p for p in self.convert(pages).splitlines() if p.startswith('<p')]
        self.assertEqual(1, len([p for p in paras if 'Caption of the image' in p]))
        for p in paras:
            if 'Caption of the image' in p:
                self.assertNotIn('The heading after the caption', p)

    def paragraph_texts(self, html: str) -> list[str]:
        from calibre.utils.xml_parse import safe_xml_fromstring

        return [''.join(p.itertext()) for p in safe_xml_fromstring(html).xpath('//*[local-name()="p"]')]

    def paragraphs_page(self, line_counts: Sequence[int], top: int = 223, line_gap: int = 35, para_gap: int = 50) -> tuple[list[FontFragment], int]:
        """
        Body text paragraphs of the given numbers of lines, without indents.
        The last line of each paragraph is wide enough that only the gap
        before the next paragraph keeps them apart. Returns the fragments and
        the top of the line after the last paragraph.
        """
        ans: list[FontFragment] = []
        for p, count in enumerate(line_counts):
            for i in range(count):
                last = i == count - 1
                ans.append((337, top, 800 if last else 1100, f'Paragraph{p} line {i} {self.BODY}', 0))
                top += para_gap if last else line_gap
        return ans, top

    def assert_paragraphs_kept(self, html: str, line_counts: Sequence[int]) -> None:
        paras = self.paragraph_texts(html)
        for p, count in enumerate(line_counts):
            matching = [x for x in paras if f'Paragraph{p} ' in x]
            self.assertEqual(1, len(matching), f'Paragraph{p} is split or missing in: {paras}')
            self.assertEqual(count, matching[0].count(self.BODY), f'Paragraph{p} lines not all joined: {matching[0]}')
            self.assertEqual({f'Paragraph{p}'}, set(re.findall(r'Paragraph\d+', matching[0])), f'Paragraph{p} merged with another: {matching[0]}')

    def test_compact_text_does_not_split_body_paragraphs(self) -> None:
        # Lines in a smaller font, such as code listings, set closer together
        # than the body text must not be mistaken for the body line spacing,
        # which would split every line of body text into its own paragraph
        line_counts = (4, 4, 4)
        page, top = self.paragraphs_page(line_counts)
        page += [(337, top + i * 29, 300, f'(code line {i})', 2) for i in range(8)]
        html = self.convert([page])
        self.assert_paragraphs_kept(html, line_counts)
        paras = self.paragraph_texts(html)
        for i in range(8):
            matching = [x for x in paras if f'(code line {i})' in x]
            self.assertEqual([f'(code line {i})'], [x.strip() for x in matching], paras)

    def test_short_paragraphs_with_frequent_paragraph_gaps(self) -> None:
        # When most paragraphs are a single line, the gap between paragraphs
        # is more common than the gap between lines, and must still separate
        # paragraphs rather than be treated as the line spacing
        line_counts = (2, 1, 1) * 5
        page, _ = self.paragraphs_page(line_counts, top=100)
        self.assert_paragraphs_kept(self.convert([page]), line_counts)

    def test_line_gaps_smaller_than_the_text_height(self) -> None:
        # The height of text is that of its font's bounding box, which can be
        # more than the gap between lines. Those gaps must still be used to
        # estimate the line spacing, otherwise only the paragraph gaps are,
        # and paragraphs are merged.
        line_counts = (3, 4, 2, 3, 5, 3)
        page, _ = self.paragraphs_page(line_counts, line_gap=25, para_gap=38)
        self.assert_paragraphs_kept(self.convert([page]), line_counts)

    def test_few_body_size_line_gaps_are_not_used_for_spacing(self) -> None:
        # A line takes the largest font size of the text in it, so lines with
        # some larger text in them are not body text lines. When that leaves
        # only the gaps between paragraphs as gaps between body text lines,
        # they are too few to determine the line spacing from.
        page: list[FontFragment] = []
        top = 223
        for p in range(3):
            for i in range(4):
                last = i == 3
                page.append((337, top, 600, f'Paragraph{p} line {i} {self.BODY}', 0))
                page.append((950, top, 400, 'LARGER', 1) if i in (1, 2) else (950, top, 100 if last else 400, 'tail', 0))
                top += 50 if last else 35
        html = self.convert([page])
        found = [x for x in self.paragraph_texts(html) if 'Paragraph' in x]
        self.assertEqual(3, len(found), found)
        for p, text in enumerate(found):
            self.assertEqual({f'Paragraph{p}'}, set(re.findall(r'Paragraph\d+', text)), found)
            self.assertEqual(4, text.count(self.BODY), found)


class TestLineAndParaSpace(unittest.TestCase):
    """
    The line and paragraph spacing are estimated from how often each gap
    between the tops of consecutive lines occurs.
    """

    def check(self, spaces: dict[float, int], expected: tuple[float, float]) -> None:
        self.assertEqual(expected, line_and_para_space(spaces))
        # The order the gaps were first seen in must not matter
        self.assertEqual(expected, line_and_para_space(dict(reversed(spaces.items()))))

    def test_nearby_gaps_are_one_spacing(self) -> None:
        # Lines are joined up to the largest common gap in the line spacing,
        # rounding spreads it over neighbouring values
        self.check({18: 3500, 19: 2800, 20: 2300, 36: 700, 28: 600}, (20, 36))

    def test_rare_nearby_gaps_are_not_part_of_the_spacing(self) -> None:
        self.check({18: 1000, 21: 5, 30: 100}, (18, 30))
        # Nor are less common paragraph gaps close to the line spacing
        self.check({18: 1000, 19: 150, 22: 200}, (18, 22))

    def test_paragraph_spacing_is_its_most_common_gap(self) -> None:
        # Paragraph gaps spread over a wider range, and the paragraph spacing
        # is multiplied up to find section breaks, so it is not the largest
        self.check({18: 666, 17: 59, 27: 86, 30: 77, 24: 55, 25: 45, 39: 21}, (18, 27))
        # The smaller of equally common gaps
        self.check({20: 100, 30: 20, 32: 20}, (20, 30))

    def test_line_gaps_are_not_paragraph_gaps(self) -> None:
        # Gaps up to the limit for joining lines are never the paragraph
        # spacing, even when they are less common than it
        self.check({20: 100, 22: 9, 23: 8, 34: 7}, (20, 34))
        self.check({30: 100, 34: 30, 50: 20}, (30, 50))

    def test_gaps_next_to_the_line_spacing_are_not_paragraph_gaps(self) -> None:
        # Code in the body font size, more closely spaced than the prose, so
        # that the line spacing band spans both, with the prose line gaps just
        # above it. They must not be taken for the paragraph spacing, which
        # would make every paragraph gap a section break.
        self.check({21: 252, 25: 249, 22: 155, 41: 97, 46: 84, 24: 82, 40: 79, 45: 67, 64: 43}, (24, 41))

    def test_gaps_just_below_the_line_spacing_are_not_line_gaps(self) -> None:
        self.check({20: 100, 19: 60, 16: 50, 34: 20}, (20, 34))

    def test_equally_common_gaps(self) -> None:
        # Equally common gaps must all be considered, whatever their order
        self.check({41: 147, 42: 34, 25: 34, 40: 11}, (25, 41))
        self.check({20: 50, 30: 50}, (20, 30))

    def test_paragraph_gaps_more_common_than_line_gaps(self) -> None:
        # Many short paragraphs make the paragraph gap the most common one,
        # and the line spacing is the largest in its band
        self.check({50: 42, 35: 12}, (35, 50))
        self.check({30: 100, 20: 40, 21: 30}, (21, 30))
        self.check({27: 1968, 18: 1764, 17: 228, 31: 548, 30: 443}, (18, 27))

    def test_rare_smaller_gaps_are_not_line_gaps(self) -> None:
        # A few gaps smaller than the line spacing must not replace it, which
        # would make every line a paragraph, but larger ones can still be the
        # paragraph spacing
        self.check({50: 100, 35: 5}, (50, 90))
        self.check({25: 1000, 20: 3, 50: 40}, (25, 45))
        self.check({25: 1000, 20: 60, 40: 40}, (25, 40))
        self.check({25: 1000, 20: 30, 40: 40}, (25, 40))

    def test_no_paragraph_spacing(self) -> None:
        # Indented paragraphs have no paragraph gaps, so rare larger gaps are
        # not the paragraph spacing, which is then a multiple of the line spacing
        self.check({44: 70, 38: 1, 60: 2}, (44, 79))
        self.check({20: 10, 30: 2}, (20, 36))
        self.check({20: 1000, 30: 20}, (20, 36))
        self.check({20: 100}, (20, 36))
        self.check({}, (0, 0))

    def test_paragraph_spacing_from_its_whole_band(self) -> None:
        # Long paragraphs have few paragraph gaps, spread over nearby values
        self.check({20: 1000, 30: 40}, (20, 30))
        self.check({20: 100, 33: 2, 34: 2, 35: 2}, (20, 33))

    def test_paragraph_spacing_is_limited(self) -> None:
        self.check({20: 100, 60: 30}, (20, 36))


class TestImages(unittest.TestCase):
    """
    The size of an image in the PDF is only meaningful relative to the page, and
    readers must be able to shrink it to fit the screen without distorting it.
    """

    def html(self, width: int, height: int, page_width: int = 1800, page_height: int = 1349) -> str:
        from calibre.utils.logging import default_log
        from calibre.utils.xml_parse import safe_xml_fromstring

        img = safe_xml_fromstring(f'<image top="10" left="10" width="{width}" height="{height}" src="x.jpg"/>')
        return Image(img, page_width, page_height, Opts(), default_log, iter(range(10))).to_html()

    def test_size_is_not_fixed(self) -> None:
        html = self.html(1313, 984)
        self.assertNotIn('width=', html)
        self.assertNotIn('height', html)

    def test_small_image_keeps_its_size_relative_to_the_page(self) -> None:
        self.assertIn('style="max-width:20%"', self.html(360, 200))

    def test_large_image_can_fill_the_screen(self) -> None:
        # Fills the height of a landscape page but not its width
        self.assertIn('style="max-width:100%"', self.html(721, 900))
        self.assertIn('style="max-width:100%"', self.html(1313, 300))


class TestPageAnchorsSurviveHeuristics(unittest.TestCase):
    """
    Each page starts with an element whose id is the target of Table of
    Contents entries for that page, heuristic processing must not lose it.
    """

    def processor(self) -> HeuristicProcessor:
        from calibre.ebooks.conversion.utils import HeuristicProcessor
        from calibre.utils.logging import default_log

        return HeuristicProcessor(None, default_log)

    def test_unwrapping_a_sentence_across_pages(self) -> None:
        html = '<p>The previous page ends in the middle of a sentence</p>\n<p id="page_2">that continues here.</p>'
        ans = self.processor().punctuation_unwrap(5, html, 'html')
        self.assertEqual(ans, '<p>The previous page ends in the middle of a sentence <a id="page_2"></a>that continues here.</p>')

    def test_unwrapping_keeps_ids_of_removed_and_retained_tags(self) -> None:
        html = "<p>The previous page ends in the middle of a sentence</p>\n<p id='a\"b'><i id=\"x\">that</i> continues here.</p>"
        ans = self.processor().punctuation_unwrap(5, html, 'html')
        self.assertEqual(ans, '<p>The previous page ends in the middle of a sentence <a id=\'a"b\'></a><i id="x">that</i> continues here.</p>')

    def test_dehyphenating_a_word_across_pages(self) -> None:
        from calibre.ebooks.conversion.preprocess import Dehyphenator
        from calibre.utils.logging import default_log

        html = '<p>The previous page ends in the middle of a hyphen-</p>\n<p id="page_2">ated word and the hyphenated text.</p>'
        ans = Dehyphenator(0, default_log)(html, 'html', 5)
        self.assertEqual(ans, '<p>The previous page ends in the middle of a <a id="page_2"></a>hyphenated word and the hyphenated text.</p>')
        # The hyphen is kept for words not found elsewhere in the text
        html = '<p>The previous page ends in the middle of a hyphen-</p>\n<p id="page_2">ated word.</p>'
        ans = Dehyphenator(0, default_log)(html, 'html', 5)
        self.assertEqual(ans, '<p>The previous page ends in the middle of a <a id="page_2"></a>hyphen-ated word.</p>')

    def test_restyled_heading(self) -> None:
        html = '<p>Text.</p>\n<p> </p>\n<h2 id="page_3" style="text-align:right">A heading</h2>\n<p> </p>\n<p>More text.</p>'
        ans = self.processor().detect_whitespace(html)
        self.assertIn('<h2 id="page_3" style="margin-top:1em;margin-bottom:1em;">A heading</h2>', ans)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromNames([
        f'{__name__}.{x.__name__}'
        for x in (
            TestSingleColumn,
            TestColumnDetection,
            TestSpanningElements,
            TestTables,
            TestRightToLeftColumns,
            TestPageBoundaries,
            TestLineAndParaSpace,
            TestImages,
            TestPageAnchorsSurviveHeuristics,
        )
    ])


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
