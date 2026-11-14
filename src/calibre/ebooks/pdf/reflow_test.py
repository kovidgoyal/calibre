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

from calibre.ebooks.pdf.reflow import Image, Page, PDFDocument
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.icu import logical_to_visual

if TYPE_CHECKING:
    from collections.abc import Sequence

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
            TestImages,
        )
    ])


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
