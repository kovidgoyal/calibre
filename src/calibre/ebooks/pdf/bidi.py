#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
poppler's pdftohtml outputs the text of a line in visual order, that is, in the
order the glyphs are painted on the page, from left to right. For right-to-left
scripts such as Hebrew, Arabic, Persian and Urdu that is the reverse of logical
(storage) order, so such PDFs convert to unreadable output. pdftotext runs the
bidirectional algorithm and does not suffer from this, but the HTML/XML output
device in poppler does not, so we have to undo the visual ordering ourselves.

The reordering itself is done by ICU, which calibre already links against, via
calibre.utils.icu.visual_to_logical(). ICU implements the inverse of the
Unicode bidirectional algorithm, so it detects the base direction of each line,
keeps runs of numbers and Latin text that are embedded in right-to-left text
the right way round, and mirrors brackets, all per the Unicode standard.

What this module adds on top is the ability to reorder a line that has inline
markup in it, which ICU knows nothing about. A line is broken into runs of
text, each remembering the tags it is nested inside, the runs are reordered as
a unit, and the markup is then rebuilt around them. Elements with no text in
them, such as anchors and images, take part in the reordering as neutral
objects, so that they end up in the right place too.

Note that if poppler ever fixes its HTML output device to emit logical order,
this would double reverse and would need to be gated on the poppler version.
"""

import re
from html import escape, unescape

from calibre.utils.icu import visual_to_logical as icu_visual_to_logical

# Cheap pre-filter, the blocks containing right-to-left scripts. Used to avoid
# running the full bidirectional algorithm over left-to-right text. Covers
# every character with a bidi class of R or AL.
HAS_RTL_PAT = re.compile(
    # Hebrew, Arabic, Syriac, Thaana, NKo, Samaritan, Mandaic, Arabic Extended
    r'[\u0590-\u08ff'
    # The right-to-left mark
    r'\u200f'
    # Hebrew and Arabic presentation forms
    r'\ufb1d-\ufdff\ufe70-\ufefc'
    # Cypriot, Phoenician, Kharoshthi, Avestan, Adlam and the rest
    r'\U00010800-\U00010fff\U0001e800-\U0001ecbf\U0001ed00-\U0001eeff]'
)

OBJECT_REPLACEMENT = '\ufffc'

# Elements that never have any text content, so are always treated as objects
VOID_TAGS = frozenset({'br', 'hr', 'img', 'image', 'input', 'meta', 'link'})

TOKEN_PAT = re.compile(r'<[^>]*>')
TAG_NAME_PAT = re.compile(r'<\s*(/?)\s*([a-zA-Z][-a-zA-Z0-9:]*)')


def has_rtl(text: str) -> bool:
    "Does text contain any right-to-left characters?"
    return HAS_RTL_PAT.search(text) is not None


def is_predominantly_rtl(text: str) -> bool:
    "Is most of the strongly directional text in text right-to-left?"
    if not has_rtl(text):
        return False
    import unicodedata

    rtl = ltr = 0
    for c in text:
        d = unicodedata.bidirectional(c)
        if d in ('R', 'AL'):
            rtl += 1
        elif d == 'L':
            ltr += 1
    return rtl > ltr


def visual_to_logical(text: str) -> str:
    "Convert a line of plain text from visual to logical order"
    if not has_rtl(text):
        return text
    return icu_visual_to_logical(text)


# Reordering runs of text {{{


def reorder_runs(runs: list, convert=icu_visual_to_logical) -> list:
    """
    Reorder runs, a list of (text, context) pairs making up a single line in
    visual order, into logical order. context is opaque to this function, it
    simply travels with the text it belongs to. Returns a new list of
    (text, context) pairs, in logical order. A run whose characters do not stay
    together is split into several runs sharing the same context.

    convert is the reordering function to use. It exists so that the transform
    can be run in the opposite direction, which the tests use to check that
    reordering a rendered line recovers the line it was rendered from.
    """
    if len(runs) == 1:
        text, context = runs[0]
        return [(convert(text), context)]
    # Which run each character of the line came from
    owners: list[int] = []
    for i, (text, context) in enumerate(runs):
        owners.extend([i] * len(text))
    line = ''.join(text for text, context in runs)
    logical, index_map = convert(line, True)
    ans: list = []
    current: list[str] = []
    current_owner = 0
    for i, ch in enumerate(logical):
        src = index_map[i]
        # A source index of -1 means the character has no counterpart in the
        # input, so keep it with the run being built rather than dropping it
        owner = owners[src] if 0 <= src < len(owners) else current_owner
        if owner != current_owner:
            if current:
                ans.append((''.join(current), runs[current_owner][1]))
            current = []
            current_owner = owner
        current.append(ch)
    if current:
        ans.append((''.join(current), runs[current_owner][1]))
    return ans


# }}}

# Parsing a line of markup into a tree {{{


class Elem:
    "An element with inline markup, such as <b>...</b>"

    def __init__(self, open_tag: str, name: str):
        self.open_tag = open_tag
        self.name = name
        self.children: list = []

    @property
    def close_tag(self) -> str:
        return f'</{self.name}>'

    def has_text(self) -> bool:
        for child in self.children:
            if isinstance(child, str):
                if child:
                    return True
            elif isinstance(child, Elem):
                if child.has_text():
                    return True
        return False

    def markup(self) -> str:
        parts = [self.open_tag]
        for child in self.children:
            parts.append(child if isinstance(child, str) else child.markup())
        parts.append(self.close_tag)
        return ''.join(parts)


class Atom:
    "A piece of markup with no text in it, such as an image or an anchor"

    def __init__(self, markup: str, is_marker: bool = False):
        self.raw = markup
        # A marker is an anchor that is the target of a link rather than
        # something that is drawn on the page. It has no glyphs, so unlike an
        # image it does not take part in the reordering, it stays at the edge
        # of the line it was at, which is what keeps the generated table of
        # contents pointing at the right place.
        self.is_marker = is_marker


def is_link_target(elem) -> bool:
    "Is elem an anchor that exists only to be linked to, rather than content?"
    return elem.name == 'a' and 'href' not in elem.open_tag.lower()


def is_object_run(run: tuple) -> bool:
    "Is run an element standing in for an object rather than text?"
    context = run[1]
    return bool(context) and isinstance(context[-1], Atom)


def is_marker_run(run: tuple) -> bool:
    "Is run a link target rather than something drawn on the page?"
    return is_object_run(run) and run[1][-1].is_marker


def tag_name(token: str) -> tuple[str, bool]:
    "The name of the tag in token and whether it is a closing tag"
    m = TAG_NAME_PAT.match(token)
    if m is None:
        return '', False
    return m.group(2).lower(), bool(m.group(1))


def parse_markup(raw: str) -> list:
    """
    Parse a line of inline markup into a list of strings, Elem and Atom. Markup
    that does not nest properly is kept as-is rather than being rearranged, so
    that a malformed line can never lose text.
    """
    root = Elem('', '')
    stack = [root]
    pos = 0
    for m in TOKEN_PAT.finditer(raw):
        if m.start() > pos:
            stack[-1].children.append(raw[pos : m.start()])
        pos = m.end()
        token = m.group()
        name, is_close = tag_name(token)
        if not name:  # a comment, doctype or processing instruction
            stack[-1].children.append(Atom(token))
        elif name in VOID_TAGS or token.endswith('/>'):
            stack[-1].children.append(Atom(token))
        elif is_close:
            # Find the matching open tag, ignoring the close tag if there is
            # none, as closing an element we never opened would lose text
            for i in range(len(stack) - 1, 0, -1):
                if stack[i].name == name:
                    del stack[i + 1 :]
                    stack.pop()
                    break
            else:
                stack[-1].children.append(Atom(token))
        else:
            elem = Elem(token, name)
            stack[-1].children.append(elem)
            stack.append(elem)
    if pos < len(raw):
        stack[-1].children.append(raw[pos:])
    return root.children


def flatten(nodes: list, context: tuple, runs: list) -> None:
    "Flatten nodes into runs of (text, context), context being the enclosing elements"
    for node in nodes:
        if isinstance(node, str):
            if node:
                runs.append((unescape(node), context))
        elif isinstance(node, Atom):
            runs.append((OBJECT_REPLACEMENT, context + (node,)))
        elif node.has_text():
            flatten(node.children, context + (node,), runs)
        else:
            # An element with no text in it, such as <a id="p1"></a>. Keep it
            # in one piece and let it take part in the reordering as an object.
            runs.append((OBJECT_REPLACEMENT, context + (Atom(node.markup(), is_link_target(node)),)))


def rebuild(runs: list) -> str:
    "Rebuild markup from runs of (text, context), the inverse of flatten()"
    ans: list[str] = []
    open_context: tuple = ()
    for text, context in runs:
        # An Atom is always the last item of its context and is never left open
        atom = context[-1] if context and isinstance(context[-1], Atom) else None
        elems = context[:-1] if atom is not None else context
        common = 0
        while common < len(open_context) and common < len(elems) and open_context[common] is elems[common]:
            common += 1
        for elem in reversed(open_context[common:]):
            ans.append(elem.close_tag)
        for elem in elems[common:]:
            ans.append(elem.open_tag)
        open_context = elems
        if atom is not None:
            ans.append(atom.raw)
        else:
            ans.append(escape(text, quote=False))
    for elem in reversed(open_context):
        ans.append(elem.close_tag)
    return ''.join(ans)


def fix_markup_line(raw: str, convert=icu_visual_to_logical) -> str:
    """
    Convert a single line of markup, as generated by pdftohtml, from visual to
    logical order. The text of the line is reordered as a whole, across any
    inline markup in it, so that a phrase that is split up by a change of style
    or by being in several fragments is still reordered correctly. See
    reorder_runs() for convert.
    """
    if not has_rtl(raw):
        return raw
    runs: list = []
    flatten(parse_markup(raw), (), runs)
    if not runs:
        return raw
    # Anchors at either end of the line are link targets rather than content,
    # so they are held where they are instead of being reordered. pdftohtml
    # puts one at the start of every page and the generated table of contents
    # links to it, so it has to stay at the start.
    start = 0
    while start < len(runs) and is_marker_run(runs[start]):
        start += 1
    end = len(runs)
    while end > start and is_marker_run(runs[end - 1]):
        end -= 1
    return rebuild(runs[:start] + reorder_runs(runs[start:end], convert) + runs[end:])


def markup_to_text(raw: str) -> str:
    "The text of a line of markup, with the markup removed"
    runs: list = []
    flatten(parse_markup(raw), (), runs)
    return ''.join(run[0] for run in runs if not is_object_run(run))


# }}}

# The pdftohtml HTML output {{{

# pdftohtml puts every line of text on its own, separated by these
LINE_BREAK_PAT = re.compile(r'<\s*(?:br|hr)\b[^>]*>', re.IGNORECASE)
BODY_PAT = re.compile(r'(<body[^>]*>)(.*)(</body\s*>)', re.IGNORECASE | re.DOTALL)
HTML_OPEN_PAT = re.compile(r'<html(?=[\s>])[^>]*>', re.IGNORECASE)


def fix_pdftohtml_html(raw: str) -> str:
    """
    Convert the right-to-left lines of the HTML generated by pdftohtml from
    visual to logical order. Also marks the document as right-to-left if it is
    predominantly so, without which the punctuation still renders on the wrong
    side.
    """
    if not has_rtl(raw):
        return raw
    m = BODY_PAT.search(raw)
    if m is None:
        return raw
    body = m.group(2)
    pos, parts = 0, []
    for sep in LINE_BREAK_PAT.finditer(body):
        parts.append(fix_markup_line(body[pos : sep.start()]))
        parts.append(sep.group())
        pos = sep.end()
    parts.append(fix_markup_line(body[pos:]))
    body = ''.join(parts)
    raw = raw[: m.start()] + m.group(1) + body + m.group(3) + raw[m.end() :]
    if is_predominantly_rtl(markup_to_text(body)):
        # On the html element rather than the body as pdftohtml_rules() in
        # conversion/preprocess.py throws away the attributes of the body
        hm = HTML_OPEN_PAT.search(raw)
        if hm is not None and ' dir=' not in hm.group().lower():
            tag = hm.group()[:-1].rstrip()
            if tag.endswith('/'):
                tag = tag[:-1].rstrip()
                end = '/>'
            else:
                end = '>'
            raw = raw[: hm.start()] + tag + ' dir="rtl"' + end + raw[hm.end() :]
    return raw


# }}}
