#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Tests for converting the visual order text pdftohtml produces back into
logical order.

The strings in these tests are written in logical order, the way they are in
the PDF, and the visual order pdftohtml would emit for them is produced by
running the Unicode bidirectional algorithm forwards, which is exactly what a
PDF renderer does when it paints the glyphs. The test is then that converting
that visual order text back recovers the string we started with.
"""

import unicodedata
import unittest

from calibre.ebooks.pdf.bidi import (
    OBJECT_REPLACEMENT,
    fix_markup_line,
    fix_pdftohtml_html,
    flatten,
    has_rtl,
    is_predominantly_rtl,
    markup_to_text,
    parse_markup,
    rebuild,
    reorder_runs,
    visual_to_logical,
)
from calibre.utils.icu import logical_to_visual
from calibre.utils.icu import visual_to_logical as icu_visual_to_logical

# Strings in logical order, covering the right-to-left scripts and the things
# that are easy to get wrong when reordering them
HEBREW = 'שלום עולם'
HEBREW_SENTENCE = 'יש כאן (סוגריים) בסוף.'
HEBREW_NUMBER = 'שנת 2024 טובה'
HEBREW_LATIN = 'ספר The Great Book כאן'
HEBREW_QUOTED = 'יש (see this) כאן'
ARABIC = 'مرحبا بالعالم'
ARABIC_SENTENCE = 'يوجد هنا (أقواس) في النص'
ARABIC_DIGITS = 'سنة ٢٠٢٤ كانت'
ARABIC_PUNCT = 'في النص؛ أليس كذلك؟'
ARABIC_GUILLEMETS = 'وأيضا «مزدوجة» في'
PERSIAN = 'جمله فارسی با (پرانتز) است'
PERSIAN_DIGITS = 'سال ۱۴۰۳ بود'
URDU = 'یہ ایک کتاب ہے'
SYRIAC = 'ܐܠܗܐ ܒܪܐ'
THAANA = 'ދިވެހި ބަސް'
NKO = 'ߒߞߏ ߞߊ߲'
ENGLISH = 'The quick brown fox'
ENGLISH_HEBREW = 'The word שלום here'
ENGLISH_HEBREW_PARENS = 'See Genesis (בראשית) chapter 1'

RTL_LINES = (
    HEBREW, HEBREW_SENTENCE, HEBREW_NUMBER, HEBREW_LATIN, HEBREW_QUOTED,
    ARABIC, ARABIC_SENTENCE, ARABIC_DIGITS, ARABIC_PUNCT, ARABIC_GUILLEMETS,
    PERSIAN, PERSIAN_DIGITS, URDU, SYRIAC, THAANA, NKO,
)
# Lines with no right-to-left characters in them at all
PURE_LTR_LINES = (ENGLISH, '', '   ', '12345', 'a<b')
# Lines whose base direction is left to right but which quote right-to-left text
MIXED_LTR_LINES = (ENGLISH_HEBREW, ENGLISH_HEBREW_PARENS)
LTR_LINES = PURE_LTR_LINES + MIXED_LTR_LINES

ALL_LINES = RTL_LINES + LTR_LINES


def render(logical: str) -> str:
    "The visual order a PDF renderer, and so pdftohtml, produces for logical"
    return logical_to_visual(logical)


def render_markup(logical: str) -> str:
    "As render() but for a line that has inline markup in it"
    return fix_markup_line(logical, logical_to_visual)


class TestICUBidi(unittest.TestCase):
    "The ICU primitive the rest of the module is built on"

    def test_round_trip(self):
        for logical in ALL_LINES:
            visual = render(logical)
            self.assertEqual(logical, icu_visual_to_logical(visual), f'Failed to recover: {logical!r} (visual: {visual!r})')

    def test_ltr_unchanged(self):
        # Text with no right-to-left characters in it has nothing to reorder,
        # in either direction
        for text in PURE_LTR_LINES:
            self.assertEqual(text, icu_visual_to_logical(text))
            self.assertEqual(text, logical_to_visual(text))

    def test_mixed_line_is_not_identity(self):
        # A left-to-right line that quotes right-to-left text does get
        # reordered, it is only the base direction that stays left to right
        for text in MIXED_LTR_LINES:
            self.assertNotEqual(text, logical_to_visual(text))

    def test_length_preserved(self):
        for logical in ALL_LINES:
            self.assertEqual(len(logical), len(render(logical)), f'Length changed for {logical!r}')

    def test_index_map(self):
        for logical in ALL_LINES:
            visual = render(logical)
            text, index_map = icu_visual_to_logical(visual, True)
            self.assertEqual(logical, text)
            self.assertEqual(len(text), len(index_map), f'Map length wrong for {logical!r}')
            self.assertEqual(sorted(index_map), list(range(len(text))), f'Map is not a permutation for {logical!r}')
            # Every output character comes from the input character the map
            # points at, except where mirroring replaced it
            for i, ch in enumerate(text):
                src = visual[index_map[i]]
                if ch != src:
                    self.assertTrue(unicodedata.mirrored(src), f'{src!r} became {ch!r} but is not mirrored')

    def test_astral(self):
        # Adlam is a right-to-left script outside the basic multilingual plane,
        # so its characters are surrogate pairs in the UTF-16 ICU works in
        adlam = '\U0001e922\U0001e923\U0001e924'
        logical = f'{adlam} 123 {adlam}'
        visual = render(logical)
        text, index_map = icu_visual_to_logical(visual, True)
        self.assertEqual(logical, text)
        self.assertEqual(len(text), len(index_map))
        self.assertEqual(sorted(index_map), list(range(len(text))))

    def test_empty(self):
        self.assertEqual('', icu_visual_to_logical(''))
        self.assertEqual(('', ()), icu_visual_to_logical('', True))

    def test_mirroring(self):
        # Brackets are stored mirrored in the PDF and have to be swapped back
        for opening, closing in ('()', '[]', '{}', '«»'):
            logical = f'א {opening}ב{closing} ג'
            self.assertEqual(logical, icu_visual_to_logical(render(logical)))


class TestHasRTL(unittest.TestCase):

    def test_covers_every_rtl_character(self):
        missed = []
        for cp in range(0x110000):
            c = chr(cp)
            if unicodedata.bidirectional(c) in ('R', 'AL') and not has_rtl(c):
                missed.append(f'U+{cp:04X} {unicodedata.name(c, "?")}')
        self.assertEqual([], missed, 'The pre-filter misses right-to-left characters')

    def test_no_false_positives_for_plain_text(self):
        for text in (ENGLISH, '', '12345', 'Ελληνικά', 'Русский', '日本語'):
            self.assertFalse(has_rtl(text), f'{text!r} was reported as right-to-left')

    def test_detects_rtl(self):
        for text in RTL_LINES + (ENGLISH_HEBREW,):
            self.assertTrue(has_rtl(text), f'{text!r} was not detected as containing right-to-left text')


class TestIsPredominantlyRTL(unittest.TestCase):

    def test_rtl(self):
        for text in (HEBREW, ARABIC, HEBREW_SENTENCE, HEBREW_NUMBER, PERSIAN):
            self.assertTrue(is_predominantly_rtl(text), f'{text!r} should be predominantly right-to-left')

    def test_ltr(self):
        for text in (ENGLISH, ENGLISH_HEBREW, ENGLISH_HEBREW_PARENS, '', '2024'):
            self.assertFalse(is_predominantly_rtl(text), f'{text!r} should not be predominantly right-to-left')


class TestVisualToLogical(unittest.TestCase):
    "Reordering a line of plain text"

    def test_round_trip(self):
        for logical in ALL_LINES:
            self.assertEqual(logical, visual_to_logical(render(logical)), f'Failed to recover {logical!r}')

    def test_left_to_right_text_is_untouched(self):
        # A line with no right-to-left text in it must come through byte for
        # byte unchanged, as the vast majority of PDFs are like this
        for text in (ENGLISH, '', 'a < b > c', '(parens) and [brackets]', 'Ελληνικά 123'):
            self.assertIs(text, visual_to_logical(text))

    def test_embedded_rtl_in_ltr_line(self):
        # A left-to-right line that merely quotes a right-to-left word must not
        # have its word order disturbed
        for logical in (ENGLISH_HEBREW, ENGLISH_HEBREW_PARENS, 'A book called مرحبا here'):
            self.assertEqual(logical, visual_to_logical(render(logical)))

    def test_numbers_keep_their_order(self):
        for logical in (HEBREW_NUMBER, ARABIC_DIGITS, PERSIAN_DIGITS, 'الرقم 1234 هنا'):
            visual = render(logical)
            self.assertEqual(logical, visual_to_logical(visual))

    def test_embedded_latin_phrase(self):
        for logical in (HEBREW_LATIN, HEBREW_QUOTED, 'كتاب اسمه The Arabic Book هنا'):
            self.assertEqual(logical, visual_to_logical(render(logical)))

    def test_known_visual_strings(self):
        # Spelled out rather than generated, so that a change in behaviour of
        # the round trip cannot hide a change in behaviour of the conversion
        self.assertEqual('שלום עולם', visual_to_logical('םלוע םולש'))
        self.assertEqual('יש כאן (סוגריים) בסוף.', visual_to_logical('.ףוסב (םיירגוס) ןאכ שי'))
        self.assertEqual('שנת 2024 טובה', visual_to_logical('הבוט 2024 תנש'))
        self.assertEqual('ספר The Great Book כאן', visual_to_logical('ןאכ The Great Book רפס'))


class TestParseMarkup(unittest.TestCase):

    def round_trip(self, raw):
        "Parsing and re-serializing must not change anything"
        runs: list = []
        flatten(parse_markup(raw), (), runs)
        return rebuild(runs)

    def test_round_trip(self):
        for raw in (
            'plain text',
            'text <b>bold</b> more',
            '<b>bold <i>and italic</i></b>',
            'a <a href="#x">link</a> b',
            'before <img src="x.png"/> after',
            'page <a id="p1"></a> anchor',
            '<span style="font-size:1.2em">big</span>',
            '',
        ):
            self.assertEqual(raw, self.round_trip(raw), f'Round trip changed {raw!r}')

    def test_entities_preserved(self):
        for raw in ('a &amp; b', '&lt;tag&gt;', 'x &amp; <b>y &lt; z</b>'):
            self.assertEqual(raw, self.round_trip(raw), f'Round trip changed {raw!r}')

    def test_text_free_elements_become_objects(self):
        runs: list = []
        flatten(parse_markup('a <a id="p1"></a> b'), (), runs)
        self.assertEqual(['a ', OBJECT_REPLACEMENT, ' b'], [t for t, c in runs])

    def test_malformed_markup_loses_no_text(self):
        for raw in (
            'unclosed <b>bold',
            'stray </b> close',
            '<b>overlapping <i>tags</b> here</i>',
            'a < b',
            '<b><i>deep</b>',
            'text <br> more',
        ):
            rebuilt = self.round_trip(raw)
            self.assertEqual(
                markup_to_text(raw), markup_to_text(rebuilt), f'Text was lost or changed for {raw!r} -> {rebuilt!r}'
            )

    def test_object_replacement_in_the_text_is_not_dropped(self):
        # The character used to stand in for an object while reordering can
        # also occur in the text itself, where it must survive
        self.assertEqual(OBJECT_REPLACEMENT, markup_to_text(OBJECT_REPLACEMENT))
        self.assertEqual(f'a{OBJECT_REPLACEMENT}b', markup_to_text(f'a{OBJECT_REPLACEMENT}<img src="x"/>b'))

    def test_markup_to_text(self):
        self.assertEqual('bold and italic', markup_to_text('<b>bold </b><i>and italic</i>'))
        self.assertEqual('a b', markup_to_text('a <img src="x.png"/>b'))
        self.assertEqual('a & b', markup_to_text('a &amp; b'))
        self.assertEqual('', markup_to_text('<a id="p1"></a>'))


class TestFixMarkupLine(unittest.TestCase):
    "Reordering a line that has inline markup in it"

    def test_left_to_right_lines_are_untouched(self):
        for raw in (
            'plain english text',
            'text <b>bold</b> more',
            'a <a href="#x">link</a> b',
            'a &amp; b',
            '',
        ):
            self.assertIs(raw, fix_markup_line(raw), f'{raw!r} was modified')

    def test_round_trip_plain(self):
        for logical in RTL_LINES:
            self.assertEqual(logical, fix_markup_line(render_markup(logical)))

    def test_round_trip_with_markup(self):
        for logical in (
            'שלום <b>עולם</b> כאן',
            'שלום <b>עולם <i>יפה</i></b> כאן',
            'שלום The <b>Great</b> Book עולם',
            'مرحبا <b>بالعالم</b> هنا',
            'שנת <b>2024</b> טובה',
            '<b>שלום</b> עולם',
            'שלום <span style="font-size:1.2em">עולם</span>',
        ):
            visual = render_markup(logical)
            self.assertEqual(logical, fix_markup_line(visual), f'Failed to recover {logical!r} from {visual!r}')

    def test_latin_phrase_spanning_a_style_change(self):
        # The whole line has to be reordered as a unit, otherwise the words of
        # an English phrase that is split up by a tag come out backwards
        self.assertEqual(
            'שלום The <b>Great</b> Book עולם', fix_markup_line('םלוע The <b>Great</b> Book םולש')
        )

    def test_link_targets_stay_at_the_edge_of_the_line(self):
        # pdftohtml puts an anchor at the start of every page and the generated
        # table of contents links to it, so it must not drift into the text
        self.assertEqual(
            '<a id="p1"></a>שלום עולם', fix_markup_line('<a id="p1"></a>' + render('שלום עולם'))
        )
        self.assertEqual(
            'שלום עולם<a id="p1"></a>', fix_markup_line(render('שלום עולם') + '<a id="p1"></a>')
        )

    def test_several_link_targets_at_the_start(self):
        raw = '<a id="p1"></a><a id="p2"></a>' + render(HEBREW)
        self.assertEqual(f'<a id="p1"></a><a id="p2"></a>{HEBREW}', fix_markup_line(raw))

    def test_a_link_with_text_is_reordered_as_content(self):
        # Unlike a bare anchor, a link the reader can follow is drawn on the
        # page, so it takes its place in the reading order like any other text
        logical = 'שלום <a href="#x">עולם</a> כאן'
        self.assertEqual(logical, fix_markup_line(render_markup(logical)))

    def test_objects_are_placed_by_reading_order(self):
        # An anchor or an image in the middle of a right-to-left line has the
        # text on either side of it swapped around it
        self.assertEqual('ראשון <a id="p2"></a> שני', fix_markup_line('ינש <a id="p2"></a> ןושאר'))
        self.assertEqual('ראשון <img src="x.png"/> שני', fix_markup_line('ינש <img src="x.png"/> ןושאר'))

    def test_no_text_is_lost(self):
        for logical in RTL_LINES:
            for template in ('%s', 'a <b>%s</b> b', '%s <img src="x.png"/>', '<a id="p1"></a>%s'):
                raw = template % logical
                visual = render_markup(raw)
                fixed = fix_markup_line(visual)
                self.assertEqual(
                    sorted(markup_to_text(visual)), sorted(markup_to_text(fixed)),
                    f'Characters were lost or added for {raw!r}',
                )

    def test_entities_survive(self):
        fixed = fix_markup_line(render_markup('שלום &amp; עולם'))
        self.assertEqual('שלום &amp; עולם', fixed)
        self.assertEqual('שלום & עולם', markup_to_text(fixed))

    def test_malformed_markup_loses_no_text(self):
        for raw in ('םולש <b>םלוע', 'םולש </b> םלוע', '<b><i>םולש</b> םלוע'):
            self.assertEqual(
                sorted(markup_to_text(raw)), sorted(markup_to_text(fix_markup_line(raw))),
                f'Text was lost for {raw!r}',
            )


class TestReorderRuns(unittest.TestCase):

    def test_context_travels_with_text(self):
        runs = [('םולש', 'a'), (' The Book ', 'b'), ('םלוע', 'c')]
        ans = reorder_runs(runs)
        self.assertEqual('עולם The Book שלום', ''.join(t for t, c in ans))
        # Each piece of text keeps the context it came in with
        for text, context in ans:
            if 'The' in text or 'Book' in text:
                self.assertEqual('b', context)

    def test_no_runs(self):
        self.assertEqual([], reorder_runs([]))

    def test_no_text_is_ever_dropped(self):
        for logical in RTL_LINES:
            runs = [(c, i) for i, c in enumerate(render(logical))]
            self.assertEqual(logical, ''.join(t for t, c in reorder_runs(runs)))

    def test_single_run(self):
        self.assertEqual([('שלום עולם', 'ctx')], reorder_runs([('םלוע םולש', 'ctx')]))

    def test_run_split_across_output(self):
        # The two spaces of this run end up on either side of the Latin phrase,
        # so the run has to be emitted in more than one piece
        runs = [('םולש', 'a'), (' ', 'b'), ('The Book', 'c'), (' ', 'b'), ('םלוע', 'd')]
        ans = reorder_runs(runs)
        self.assertEqual('עולם The Book שלום', ''.join(t for t, c in ans))


class TestFixPDFToHTML(unittest.TestCase):
    "The whole HTML document produced by pdftohtml"

    def doc(self, body, html_attrs=''):
        return f'<!DOCTYPE html>\n<html{html_attrs}>\n<head><title>t</title></head>\n<body>{body}</body>\n</html>\n'

    def test_left_to_right_document_is_untouched(self):
        raw = self.doc('first line<br>second line<br>')
        self.assertIs(raw, fix_pdftohtml_html(raw))

    def test_lines_are_reordered_independently(self):
        raw = self.doc(f'{render("שלום עולם")}<br>{render("יש כאן")}<br>')
        self.assertIn('שלום עולם<br>', fix_pdftohtml_html(raw))
        self.assertIn('יש כאן<br>', fix_pdftohtml_html(raw))

    def test_lines_are_not_run_together(self):
        # Text on one line must never be mixed into the line next to it
        raw = self.doc(f'{render(HEBREW)}<br>{render(ARABIC)}<br>')
        ans = fix_pdftohtml_html(raw)
        self.assertIn(f'{HEBREW}<br>', ans)
        self.assertIn(f'{ARABIC}<br>', ans)

    def test_dir_is_set_on_the_html_element(self):
        # pdftohtml_rules() in conversion/preprocess.py throws away the
        # attributes of body, so dir has to go on the root element
        ans = fix_pdftohtml_html(self.doc(f'{render(HEBREW)}<br>'))
        self.assertIn('<html dir="rtl">', ans)

    def test_dir_preserves_existing_attributes(self):
        ans = fix_pdftohtml_html(self.doc(f'{render(HEBREW)}<br>', ' lang="he"'))
        self.assertIn('<html lang="he" dir="rtl">', ans)

    def test_dir_not_set_for_a_mostly_english_document(self):
        ans = fix_pdftohtml_html(self.doc(f'{render(ENGLISH_HEBREW)}<br>{ENGLISH}<br>'))
        self.assertNotIn('dir="rtl"', ans)
        self.assertIn(f'{ENGLISH_HEBREW}<br>', ans)

    def test_existing_dir_is_not_duplicated(self):
        ans = fix_pdftohtml_html(self.doc(f'{render(HEBREW)}<br>', ' dir="rtl"'))
        self.assertEqual(1, ans.count('dir='))

    def test_markup_inside_a_line(self):
        raw = self.doc(f'{render_markup("שלום <b>עולם</b> כאן")}<br>')
        self.assertIn('שלום <b>עולם</b> כאן<br>', fix_pdftohtml_html(raw))

    def test_anchors_are_kept_at_the_start_of_the_page(self):
        # The generated table of contents links to these, so they must both
        # survive and stay where they point
        raw = self.doc(f'<a id="p1"></a>{render(HEBREW)}<br>')
        ans = fix_pdftohtml_html(raw)
        self.assertIn(f'<body><a id="p1"></a>{HEBREW}<br>', ans)

    def test_no_body(self):
        for raw in ('', 'שלום', '<html></html>'):
            fix_pdftohtml_html(raw)  # must not raise


class TestReflowIntegration(unittest.TestCase):
    """
    The reflow code splits a page into lines itself, by joining the fragments
    poppler emits. These check that the conversion happens after that, so that
    a line that arrives in several pieces is still reordered as a whole.
    """

    def page(self, fragments, page_width=600):
        from calibre.ebooks.pdf.reflow import Page
        from calibre.utils.logging import default_log
        from calibre.utils.xml_parse import safe_xml_fromstring

        class Opts:
            pdf_header_skip = 0
            pdf_footer_skip = 0
            pdf_header_regex = ''
            pdf_footer_regex = ''
            no_images = True
            verbose = 0

        parts = [f'<page number="1" top="0" left="0" height="800" width="{page_width}">']
        for left, top, width, text in fragments:
            parts.append(f'<text top="{top}" left="{left}" width="{width}" height="12">{text}</text>')
        parts.append('</page>')
        root = safe_xml_fromstring(''.join(parts))
        opts = Opts()
        page = Page(root, {}, opts, default_log, iter(range(10000)))
        page.join_fragments(opts)
        for t in page.texts:
            t.convert_visual_order_to_logical()
        return page

    def test_line_in_several_fragments(self):
        # poppler emits a line as several <text> elements. They have to be
        # joined before being reordered, otherwise the fragments of an English
        # phrase inside a Hebrew line come out backwards.
        page = self.page([
            (10, 10, 40, 'םלוע'),
            (55, 10, 30, 'The'),
            (90, 10, 45, 'Great'),
            (140, 10, 40, 'Book'),
            (185, 10, 40, 'םולש'),
        ])
        self.assertEqual(1, len(page.texts))
        self.assertEqual('שלום The Great Book עולם', page.texts[0].text_as_string)

    def test_lines_are_kept_apart(self):
        page = self.page([
            (10, 10, 40, 'םלוע'),
            (55, 10, 40, 'םולש'),
            (10, 40, 40, 'רחמ'),
        ])
        self.assertEqual(2, len(page.texts))
        self.assertEqual(['שלום עולם', 'מחר'], [t.text_as_string for t in page.texts])

    def test_geometry_is_not_disturbed(self):
        # Unlike reordering the fragments on the page, reordering the text of a
        # joined line leaves every coordinate exactly as poppler reported it
        fragments = [(10, 10, 40, 'םלוע'), (55, 10, 40, 'םולש')]
        page = self.page(fragments)
        self.assertEqual(10, page.texts[0].left)
        self.assertEqual(10, page.texts[0].top)

    def test_a_tall_initial_does_not_merge_lines(self):
        # A drop cap is much taller than the lines beside it. Line detection is
        # reflow's, so the lines below it must not be pulled into it.
        page = self.page([
            (10, 10, 30, 'א'),
            (50, 10, 60, 'תחא'),
            (50, 30, 60, 'םייתש'),
            (50, 50, 60, 'שולש'),
        ])
        self.assertEqual(3, len(page.texts))

    def test_english_page_is_unchanged(self):
        fragments = [(10, 10, 40, 'The'), (55, 10, 40, 'quick'), (100, 10, 40, 'fox')]
        page = self.page(fragments)
        self.assertEqual('The quick fox', page.texts[0].text_as_string)

    def test_text_and_raw_stay_in_step(self):
        page = self.page([(10, 10, 40, 'םלוע'), (55, 10, 40, 'םולש')])
        t = page.texts[0]
        self.assertEqual(markup_to_text(t.raw), t.text_as_string)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromNames(
        [f'{__name__}.{x.__name__}' for x in (
            TestICUBidi, TestHasRTL, TestIsPredominantlyRTL, TestVisualToLogical,
            TestParseMarkup, TestFixMarkupLine, TestReorderRuns, TestFixPDFToHTML,
            TestReflowIntegration,
        )]
    )


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=4).run(find_tests())
