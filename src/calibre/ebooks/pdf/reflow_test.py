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

import random
import unittest

from calibre.ebooks.pdf.reflow import Page
from calibre.utils.icu import logical_to_visual


class Opts:
    pdf_header_skip = 0
    pdf_footer_skip = 0
    pdf_header_regex = ''
    pdf_footer_regex = ''
    no_images = True
    verbose = 0
    unwrap_factor = 0.4


def build(fragments, width=600, height=800, join=True):
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


def two_columns(rows=6, left_text=LEFT_LINE, right_text=RIGHT_LINE):
    "A plain two column page with a gutter between x=210 and x=250"
    ans = []
    for i in range(rows):
        ans.append((10, 10 + i * 20, 200, f'{left_text} {i}'))
        ans.append((250, 10 + i * 20, 200, f'{right_text} {i}'))
    return ans


def texts_of(page):
    return [t.text_as_string for t in page.texts]


class TestSingleColumn(unittest.TestCase):
    """
    A page that is not in columns must come through exactly as it did before
    columns were looked for at all, as that is the overwhelming majority of
    PDFs.
    """

    def check_not_split(self, fragments, width=600):
        page = build(fragments, width=width)
        self.assertEqual(1, page.column_count)
        for t in page.texts:
            self.assertEqual((0, 0), t.column)
        return page

    def test_plain_page(self):
        page = self.check_not_split([(10, 10 + i * 20, 400, f'Line {i} of ordinary text') for i in range(8)])
        self.assertEqual(8, len(page.texts))

    def test_fragments_are_still_joined_into_lines(self):
        page = self.check_not_split([(10, 10, 40, 'The'), (55, 10, 40, 'quick'), (100, 10, 40, 'fox')])
        self.assertEqual(['The quick fox'], texts_of(page))

    def test_empty_page(self):
        page = build([])
        self.assertEqual(1, page.column_count)
        self.assertEqual([], page.texts)

    def test_too_few_rows_to_tell(self):
        # Two rows is not enough to know a gap is a gutter and not a wide space
        self.check_not_split([(10, 10, 200, 'Left one'), (330, 10, 200, 'Right one'), (10, 30, 200, 'Left two'), (330, 30, 200, 'Right two')])

    def test_justified_text(self):
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

    def test_block_quote_indent(self):
        fragments = [(10, 10 + i * 20, 500, f'Ordinary line {i}') for i in range(4)]
        fragments += [(120, 90 + i * 20, 380, f'Indented quotation {i}') for i in range(4)]
        fragments += [(10, 180 + i * 20, 500, f'More ordinary text {i}') for i in range(4)]
        self.check_not_split(fragments)

    def test_centred_title(self):
        fragments = [(200, 5, 200, 'A Centred Title', 20)]
        fragments += [(10, 40 + i * 20, 550, f'Body line {i}') for i in range(8)]
        self.check_not_split(fragments)

    def test_table_of_contents(self):
        # The page numbers down the right hand side line up, but they are far
        # too little text to be a column of their own
        fragments = [(10, 10 + i * 20, 300, f'Chapter {i} Of This Book') for i in range(10)]
        fragments += [(560, 10 + i * 20, 20, f'{i * 7}') for i in range(10)]
        self.check_not_split(fragments)

    def test_ragged_right_margin(self):
        # The right hand margin is empty but it is a margin, not a gutter, as
        # there is no text to the right of it
        self.check_not_split([(10, 10 + i * 20, 200 + (i % 3) * 40, f'Line {i}') for i in range(10)])


class TestColumnDetection(unittest.TestCase):
    def test_two_columns(self):
        page = build(two_columns())
        self.assertEqual(2, page.column_count)
        self.assertEqual([(0, 0)] * 6 + [(0, 1)] * 6, [t.column for t in page.texts])

    def test_columns_are_read_one_after_the_other(self):
        page = build(two_columns())
        self.assertEqual([f'{LEFT_LINE} {i}' for i in range(6)] + [f'{RIGHT_LINE} {i}' for i in range(6)], texts_of(page))

    def test_fragments_are_not_joined_across_a_gutter(self):
        # This is what used to run the two columns of a line together
        page = build(two_columns())
        self.assertEqual(12, len(page.texts))
        for text in texts_of(page):
            self.assertFalse(LEFT_LINE in text and RIGHT_LINE in text, f'The columns were run together: {text!r}')

    def test_fragments_within_a_column_are_still_joined(self):
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

    def test_three_columns(self):
        names = ('first', 'second', 'third')
        fragments = []
        for i in range(6):
            for c, x in enumerate((10, 210, 410)):
                fragments.append((x, 10 + i * 20, 180, f'text of the {names[c]} column {i}'))
        page = build(fragments)
        self.assertEqual(3, page.column_count)
        self.assertEqual([f'text of the {n} column {i}' for n in names for i in range(6)], texts_of(page))

    def test_gutters(self):
        page = build(two_columns(), join=False)
        gutters = page.find_gutters()
        self.assertEqual(1, len(gutters))
        start, end = gutters[0]
        self.assertTrue(210 <= start < end <= 250, f'Unexpected gutter: {gutters[0]}')

    def test_paragraphs_are_not_merged_across_a_gutter(self):
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

    def test_heading_over_two_columns(self):
        fragments = [(10, 5, 440, 'A Full Width Heading Over The Page', 20)] + [
            (x, 45 + i * 20, 200, f'{name} {i}') for i in range(6) for x, name in ((10, LEFT_LINE), (250, RIGHT_LINE))
        ]
        page = build(fragments)
        self.assertEqual(2, page.column_count)
        self.assertEqual('A Full Width Heading Over The Page', texts_of(page)[0])
        self.assertEqual([f'{LEFT_LINE} {i}' for i in range(6)] + [f'{RIGHT_LINE} {i}' for i in range(6)], texts_of(page)[1:])

    def test_heading_over_a_short_page(self):
        # Few enough rows that the allowance for rows crossing a gutter rounds
        # down to none, so the heading would otherwise hide the gutter
        fragments = [(10, 5, 440, 'A Full Width Heading Over The Page', 20)] + [
            (x, 45 + i * 20, 200, f'{name} {i}') for i in range(4) for x, name in ((10, LEFT_LINE), (250, RIGHT_LINE))
        ]
        page = build(fragments)
        self.assertEqual(2, page.column_count)
        self.assertEqual('A Full Width Heading Over The Page', texts_of(page)[0])

    def test_heading_in_the_middle_starts_a_new_band(self):
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

    def test_a_spanning_element_is_not_joined_to_a_column(self):
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

    def table(self, rows=12):
        ans = []
        for i in range(rows):
            ans.append((10, 10 + i * 20, 80, f'Item {i}'))
            ans.append((230, 10 + i * 20, 60, f'{i * 11}'))
            ans.append((430, 10 + i * 20, 60, f'{i * 37}'))
        return ans

    def test_a_table_is_not_split_into_columns(self):
        page = build(self.table())
        self.assertEqual(1, page.column_count)

    def test_the_rows_of_a_table_stay_together(self):
        page = build(self.table())
        self.assertEqual(12, len(page.texts))
        for i, text in enumerate(texts_of(page)):
            self.assertIn(f'Item {i}', text)
            self.assertIn(str(i * 11), text)
            self.assertIn(str(i * 37), text)

    def test_a_two_column_list_of_short_entries_is_left_alone(self):
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

    def rtl_two_columns(self, rows=6):
        ans = []
        for i in range(rows):
            ans.append((10, 10 + i * 20, 200, logical_to_visual(f'{self.RTL_LEFT} {i}')))
            ans.append((250, 10 + i * 20, 200, logical_to_visual(f'{self.RTL_RIGHT} {i}')))
        return ans

    def page(self, fragments):
        page = build(fragments)
        for t in page.texts:
            t.convert_visual_order_to_logical()
        return page

    def test_right_column_is_read_first(self):
        page = self.page(self.rtl_two_columns())
        self.assertEqual(2, page.column_count)
        self.assertEqual(
            [f'{self.RTL_RIGHT} {i}' for i in range(6)] + [f'{self.RTL_LEFT} {i}' for i in range(6)],
            texts_of(page),
        )

    def test_columns_are_not_mirrored_into_each_other(self):
        # Each column is reordered on its own, so no word of one column can
        # end up in the other
        page = self.page(self.rtl_two_columns())
        for t in page.texts:
            self.assertFalse(
                'הימני' in t.text_as_string and 'השמאלי' in t.text_as_string,
                f'The columns were run together: {t.text_as_string!r}',
            )

    def test_left_to_right_page_keeps_left_column_first(self):
        page = self.page(two_columns())
        self.assertEqual(f'{LEFT_LINE} 0', texts_of(page)[0])

    def test_mostly_english_page_with_some_hebrew_is_left_to_right(self):
        fragments = two_columns()
        fragments.append((250, 130, 200, logical_to_visual('שלום')))
        page = self.page(fragments)
        self.assertEqual(f'{LEFT_LINE} 0', texts_of(page)[0])


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromNames([
        f'{__name__}.{x.__name__}'
        for x in (
            TestSingleColumn,
            TestColumnDetection,
            TestSpanningElements,
            TestTables,
            TestRightToLeftColumns,
        )
    ])


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
