#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
poppler's pdftohtml outputs the text of a line in visual order, that is, in the
order the glyphs are painted on the page, from left to right. For right-to-left
scripts that is the reverse of logical (storage) order, so Hebrew and Arabic
come out of pdftohtml with their letters backwards. pdftotext runs the bidi
algorithm and does not suffer from this, but the HTML/XML output device in
poppler does not, so we have to undo the visual ordering ourselves.
"""

import re
import unicodedata

# Cheap pre-filter, the blocks containing right-to-left scripts. Used to avoid
# running the expensive character by character analysis on left-to-right text.
HAS_RTL_PAT = re.compile(
    r'[\u0590-\u05ff\u0600-\u07bf\u0860-\u08ff\ufb1d-\ufdff\ufe70-\ufefc'
    r'\U00010800-\U00010fff\U0001e800-\U0001ecbf\U0001ed00-\U0001eeff]'
)

# Characters that are laid out left-to-right even inside a right-to-left line
LTR_DIRECTIONS = frozenset({'L', 'EN', 'AN'})
RTL_DIRECTIONS = frozenset({'R', 'AL'})
# Characters that take their direction from their surroundings
NEUTRAL_DIRECTIONS = frozenset({'B', 'BN', 'CS', 'ES', 'ET', 'NSM', 'ON', 'S', 'WS'})

# Characters that PDF producers substitute for their mirror image when laying
# out a right-to-left line, so we have to substitute them back. Only the pairs
# that actually occur in prose, the rest of the Unicode mirrored characters are
# mathematical symbols that are mirrored by shape and not by substitution.
MIRRORED = {}
for _a, _b in (
    '()', '[]', '{}', '<>', '«»', '‹›', '⁅⁆', '⁽⁾', '₍₎', '⌈⌉', '⌊⌋', '❨❩', '❪❫', '❬❭', '❮❯', '❰❱',
    '⟦⟧', '⟨⟩', '⟪⟫', '⟬⟭', '⟮⟯', '⦃⦄', '⦅⦆', '⦇⦈', '⦉⦊', '⧼⧽', '⸂⸃', '⸄⸅', '⸉⸊', '⸌⸍', '⸜⸝', '⸠⸡', '⸢⸣', '⸤⸥',
    '〈〉', '《》', '「」', '『』', '【】', '〔〕', '〖〗', '〘〙', '〚〛', '﹙﹚', '﹛﹜', '﹝﹞', '（）', '［］', '｛｝', '｟｠', '｢｣',
    '≤≥', '≦≧', '≪≫', '≮≯', '⊂⊃', '⊆⊇', '⊏⊐', '⊑⊒', '∈∋', '∉∌', '≺≻', '≼≽', '⋘⋙',
):
    MIRRORED[_a] = _b
    MIRRORED[_b] = _a
del _a, _b


def has_rtl(text: str) -> bool:
    "Does text contain any right-to-left characters?"
    return HAS_RTL_PAT.search(text) is not None


def visual_to_logical(text: str, rtl: bool = False) -> str:
    """
    Convert a run of text extracted from a PDF in visual order into logical
    order. Text without right-to-left characters is returned unchanged unless
    rtl is True, which means the run is known to be part of a right-to-left
    line, as is the case for a run of punctuation between two Hebrew words.
    """
    if not (rtl or has_rtl(text)):
        return text
    chars = list(reversed(text))
    directions = [unicodedata.bidirectional(c) for c in chars]
    ans = []
    i = 0
    while i < len(chars):
        if directions[i] in LTR_DIRECTIONS:
            # A run of characters that is laid out left-to-right even inside a
            # right-to-left line, such as a number or an English word. It got
            # reversed along with the rest of the line, so put it back. The
            # run extends over neutral characters (spaces, punctuation) only
            # if they are followed by more left-to-right characters, trailing
            # neutrals belong to the right-to-left text around the run.
            end = j = i + 1
            while j < len(chars):
                if directions[j] in LTR_DIRECTIONS:
                    end = j + 1
                elif directions[j] not in NEUTRAL_DIRECTIONS:
                    break
                j += 1
            ans.extend(reversed(chars[i:end]))
            i = end
        else:
            ans.append(MIRRORED.get(chars[i], chars[i]))
            i += 1
    return ''.join(ans)


# Fragments on the same line that are separated by a horizontal gap larger
# than this many times the height of the line are assumed to belong to
# different columns and are re-ordered independently of each other.
COLUMN_GAP_FACTOR = 2.0

# Tags that pdftohtml uses for styling runs of text within a line. Anchors and
# images are deliberately not included, they are kept where they are, as the
# anchors are the targets of the links in the generated ToC.
INLINE_TAGS = frozenset({'b', 'i', 'em', 'strong', 'span', 'font', 'sub', 'sup'})
LINE_BREAK_TAGS = frozenset({'br', 'hr'})


def is_predominantly_rtl(text: str) -> bool:
    "Is most of the text in text written in a right-to-left script?"
    rtl = ltr = 0
    for c in text:
        d = unicodedata.bidirectional(c)
        if d in RTL_DIRECTIONS:
            rtl += 1
        elif d == 'L':
            ltr += 1
    return rtl > ltr


def flatten(elem) -> list:
    "The contents of elem as a flat list of strings and child elements"
    ans = []
    if elem.text:
        ans.append(elem.text)
    for child in elem:
        ans.append(child)
        if child.tail:
            ans.append(child.tail)
    return ans


def unflatten(elem, seq) -> None:
    "Replace the contents of elem by seq, the inverse of flatten()"
    for child in tuple(elem):
        elem.remove(child)
    elem.text = None
    last = None
    for item in seq:
        if isinstance(item, str):
            if last is None:
                elem.text = (elem.text or '') + item
            else:
                last.tail = (last.tail or '') + item
        else:
            item.tail = None
            elem.append(item)
            last = item


def reverse_inline(elem, rtl: bool = False) -> None:
    "Convert the contents of elem, which must contain only inline markup, to logical order"
    for child in elem:
        reverse_inline(child, rtl)
    seq = [visual_to_logical(x, rtl) if isinstance(x, str) else x for x in flatten(elem)]
    seq.reverse()
    unflatten(elem, seq)


def group_into_lines(fragments: list) -> list:
    """
    Group (elem, left, top, right, bottom) fragments into lines. Two fragments
    are on the same line if they overlap vertically by more than half the
    height of the shorter of the two.
    """
    lines: list = []
    for frag in sorted(fragments, key=lambda f: (f[2], f[1])):
        if lines:
            group, top, bottom = lines[-1]
            overlap = min(bottom, frag[4]) - max(top, frag[2])
            if overlap > 0.5 * min(bottom - top, frag[4] - frag[2]):
                group.append(frag)
                lines[-1] = group, min(top, frag[2]), max(bottom, frag[4])
                continue
        lines.append(([frag], frag[2], frag[4]))
    return [group for group, top, bottom in lines]


def split_into_columns(line: list) -> list:
    "Split a line at gaps wide enough to be column gutters rather than word spacing"
    ans, group = [], []
    for frag in sorted(line, key=lambda f: f[1]):
        if group:
            right = max(f[3] for f in group)
            height = max(f[4] - f[2] for f in group)
            if frag[1] - right > COLUMN_GAP_FACTOR * height:
                ans.append(group)
                group = []
        group.append(frag)
    if group:
        ans.append(group)
    return ans


def fix_pdftohtml_xml(root) -> bool:
    """
    Convert every right-to-left line of a pdftohtml XML tree from visual to
    logical order. As well as the text of the individual fragments, the x
    co-ordinates of the fragments making up such a line are mirrored about the
    line, so that ordering the fragments by their left edge, which is what the
    reflow code does, yields logical order too. Returns True if anything was
    changed.
    """
    changed = False
    for page in root.iter('page'):
        fragments = []
        for elem in page.iter('text'):
            left, top = float(elem.get('left', 0)), float(elem.get('top', 0))
            fragments.append((elem, left, top, left + float(elem.get('width', 0)), top + float(elem.get('height', 0))))
        for line in group_into_lines(fragments):
            for group in split_into_columns(line):
                if not any(has_rtl(''.join(frag[0].itertext())) for frag in group):
                    continue
                left = min(f[1] for f in group)
                right = max(f[3] for f in group)
                for elem, fleft, ftop, fright, fbottom in group:
                    reverse_inline(elem, True)
                    elem.set('left', str(round(left + right - fright)))
                changed = True
    return changed


def fix_pdftohtml_html(raw: str) -> str:
    "Convert the right-to-left lines of the HTML generated by pdftohtml from visual to logical order"
    if not has_rtl(raw):
        return raw
    from lxml import html as lhtml

    root = lhtml.fromstring(raw)
    for body in root.iter('body'):
        fix_html_body(body)
        if is_predominantly_rtl(body.text_content()):
            # On the root element rather than the body as the pdftohtml
            # pre-processing rules throw away the attributes of the body
            root.set('dir', 'rtl')
    return lhtml.tostring(root, encoding='unicode', doctype='<!DOCTYPE html>')


def fix_html_body(body) -> None:
    "Convert the text of body, which is the output of pdftohtml, line by line"
    ans: list = []
    line: list = []
    for item in flatten(body):
        if not isinstance(item, str) and item.tag in LINE_BREAK_TAGS:
            ans.extend(fix_html_line(line))
            ans.append(item)
            line = []
        else:
            line.append(item)
    ans.extend(fix_html_line(line))
    unflatten(body, ans)


def fix_html_line(line: list) -> list:
    "Reverse the runs of styled text in a single line, leaving anchors and images in place"
    if not any(has_rtl(x if isinstance(x, str) else x.text_content()) for x in line):
        return line
    ans: list = []
    run: list = []

    def flush():
        run.reverse()
        for i, x in enumerate(run):
            if isinstance(x, str):
                run[i] = visual_to_logical(x, True)
            else:
                reverse_inline(x, True)
        ans.extend(run)
        del run[:]

    for item in line:
        if isinstance(item, str) or item.tag in INLINE_TAGS:
            run.append(item)
        else:
            flush()
            ans.append(item)
    flush()
    return ans


def find_tests():
    import unittest

    class TestPDFBidi(unittest.TestCase):

        def test_visual_to_logical(self):
            # The visual order strings below are written the way pdftohtml
            # emits them: the right-to-left words reversed and the runs that
            # are laid out left-to-right, such as numbers and English words,
            # the right way round.
            def t(visual, logical):
                self.assertEqual(logical, visual_to_logical(visual), f'Failed for: {visual!r}')

            t('', '')
            t('Left to right text is not touched', 'Left to right text is not touched')
            t('שלום עולם'[::-1], 'שלום עולם')
            t('שורה שלמה בעברית.'[::-1], 'שורה שלמה בעברית.')
            t('مرحبا بالعالم'[::-1], 'مرحبا بالعالم')
            # Arabic-Indic and extended Arabic-Indic digits are laid out
            # left to right as well
            t('\u062c\u064a\u062f\u0629'[::-1] + ' \u0662\u0660\u0662\u0664 ' + '\u0633\u0646\u0629'[::-1],
              '\u0633\u0646\u0629 \u0662\u0660\u0662\u0664 \u062c\u064a\u062f\u0629')
            t('\u0628\u0648\u062f'[::-1] + ' \u06f1\u06f4\u06f0\u06f3 ' + '\u0633\u0627\u0644'[::-1],
              '\u0633\u0627\u0644 \u06f1\u06f4\u06f0\u06f3 \u0628\u0648\u062f')
            # Arabic punctuation and guillemets
            t('\u0643\u0630\u0644\u0643\u061f'[::-1] + ' \u00ab' + '\u0645\u0632\u062f\u0648\u062c\u0629'[::-1] + '\u00bb ' + '\u0641\u064a'[::-1],
              '\u0641\u064a \u00ab\u0645\u0632\u062f\u0648\u062c\u0629\u00bb \u0643\u0630\u0644\u0643\u061f')
            # A number keeps its own left to right order
            t('טובה'[::-1] + ' 2024 ' + 'שנת'[::-1], 'שנת 2024 טובה')
            # As does an English phrase, spaces within it included
            t('כאן'[::-1] + ' The Great Book ' + 'ספר'[::-1], 'ספר The Great Book כאן')
            # Brackets are stored mirrored and have to be swapped back
            t('כאן'[::-1] + ' (' + 'סוגריים'[::-1] + ') ' + 'יש'[::-1], 'יש (סוגריים) כאן')
            t('בסוף'[::-1] + ' [' + 'מרובעים'[::-1] + '] ' + 'וגם'[::-1], 'וגם [מרובעים] בסוף')
            # But not when they belong to a left to right run
            t('כאן'[::-1] + ' (see this) ' + 'יש'[::-1], 'יש (see this) כאן')

        def test_fix_pdftohtml_xml(self):
            from calibre.utils.xml_parse import safe_xml_fromstring

            def text(left, width, t):
                return f'<text top="10" left="{left}" width="{width}" height="10">{t}</text>'

            root = safe_xml_fromstring(
                '<pdf2xml><page number="1" top="0" left="0" height="100" width="200">'
                + text(10, 20, '.')
                + text(30, 40, 'עולם'[::-1])
                + text(70, 10, ' ')
                + text(80, 40, 'שלום'[::-1])
                # A second line, to check that lines are kept apart
                + '<text top="30" left="10" width="40" height="10">' + 'מחר'[::-1] + '</text>'
                + '</page></pdf2xml>'
            )
            self.assertTrue(fix_pdftohtml_xml(root))
            fragments = sorted(root.iter('text'), key=lambda t: (int(t.get('top')), int(t.get('left'))))
            self.assertEqual('שלום עולם.מחר', ''.join(f.text for f in fragments))
            # The line is still in the same place on the page
            self.assertEqual([10, 50, 60, 100, 10], [int(f.get('left')) for f in fragments])

    return unittest.TestLoader().loadTestsFromTestCase(TestPDFBidi)
