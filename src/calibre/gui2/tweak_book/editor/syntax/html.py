#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import namedtuple
from functools import partial
from qt.core import QFont, QTextBlockUserData, QTextCharFormat, QVariant

from calibre.ebooks.oeb.polish.spell import html_spell_tags, patterns, xml_spell_tags
from calibre.gui2.tweak_book import dictionaries, tprefs, verify_link
from calibre.gui2.tweak_book.editor import (
    CLASS_ATTRIBUTE_PROPERTY, LINK_PROPERTY, SPELL_LOCALE_PROPERTY, SPELL_PROPERTY,
    TAG_NAME_PROPERTY, store_locale, syntax_text_char_format
)
from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter, run_loop
from calibre.gui2.tweak_book.editor.syntax.css import (
    CSSState, CSSUserData, create_formats as create_css_formats,
    state_map as css_state_map
)
from calibre.spell.break_iterator import split_into_words_and_positions
from calibre.spell.dictionary import parse_lang_code
from calibre_extensions import html_syntax_highlighter as _speedup
from polyglot.builtins import iteritems

cdata_tags = frozenset(['title', 'textarea', 'style', 'script', 'xmp', 'iframe', 'noembed', 'noframes', 'noscript'])
normal_pat = re.compile(r'[^<>&]+')
entity_pat = re.compile(r'&#{0,1}[a-zA-Z0-9]{1,8};')
tag_name_pat = re.compile(r'/{0,1}[a-zA-Z0-9:-]+')
space_chars = ' \t\r\n\u000c'
attribute_name_pat = re.compile(r'''[^%s"'/><=]+''' % space_chars)
self_closing_pat = re.compile(r'/\s*>')
unquoted_val_pat = re.compile(r'''[^%s'"=<>`]+''' % space_chars)
cdata_close_pats = {x:re.compile(r'</%s' % x, flags=re.I) for x in cdata_tags}
nbsp_pat = re.compile('[\xa0\u2000-\u200A\u202F\u205F\u3000\u2011-\u2015\uFE58\uFE63\uFF0D]+')  # special spaces and hyphens

NORMAL = 0
IN_OPENING_TAG = 1
IN_CLOSING_TAG = 2
IN_COMMENT = 3
IN_PI = 4
IN_DOCTYPE = 5
ATTRIBUTE_NAME = 6
ATTRIBUTE_VALUE = 7
SQ_VAL = 8
DQ_VAL = 9
CDATA = 10
CSS = 11

TagStart = namedtuple('TagStart', 'offset prefix name closing is_start')
TagEnd = namedtuple('TagEnd', 'offset self_closing is_start')
NonTagBoundary = namedtuple('NonTagBoundary', 'offset is_start type')
Attr = namedtuple('Attr', 'offset type data')

LINK_ATTRS = frozenset(('href', 'src', 'poster', 'xlink:href'))

do_spell_check = False


def refresh_spell_check_status():
    global do_spell_check
    do_spell_check = tprefs['inline_spell_check'] and hasattr(dictionaries, 'active_user_dictionaries')


Tag = _speedup.Tag
bold_tags, italic_tags = _speedup.bold_tags, _speedup.italic_tags
State = _speedup.State


def spell_property(sfmt, locale):
    s = QTextCharFormat(sfmt)
    s.setProperty(SPELL_LOCALE_PROPERTY, QVariant(locale))
    return s


def sanitizing_recognizer():
    sanitize = patterns().sanitize_invisible_pat.sub
    r = dictionaries.recognized

    def recognized(word, locale=None):
        word = sanitize('', word).strip()
        return r(word, locale)

    return recognized


_speedup.init(spell_property, sanitizing_recognizer(), split_into_words_and_positions)
del spell_property
check_spelling = _speedup.check_spelling


def finish_opening_tag(state, cdata_tags):
    state.parse = NORMAL
    if state.tag_being_defined is None:
        return
    t, state.tag_being_defined = state.tag_being_defined, None
    state.tags.append(t)
    state.is_bold = state.is_bold or t.bold
    state.is_italic = state.is_italic or t.italic
    state.current_lang = t.lang or state.current_lang
    if t.name in cdata_tags:
        state.parse = CSS if t.name == 'style' else CDATA
        state.sub_parser_state = None


def close_tag(state, name):
    removed_tags = []
    for tag in reversed(state.tags):
        removed_tags.append(tag)
        if tag.name == name:
            break
    else:
        return  # No matching open tag found, ignore the closing tag
    # Remove all tags up to the matching open tag
    state.tags = state.tags[:-len(removed_tags)]
    state.sub_parser_state = None
    # Check if we should still be bold or italic
    if state.is_bold:
        state.is_bold = False
        for tag in reversed(state.tags):
            if tag.bold:
                state.is_bold = True
                break
    if state.is_italic:
        state.is_italic = False
        for tag in reversed(state.tags):
            if tag.italic:
                state.is_italic = True
                break
    # Set the current language to the first lang attribute in a still open tag
    state.current_lang = None
    for tag in reversed(state.tags):
        if tag.lang is not None:
            state.current_lang = tag.lang
            break


class HTMLUserData(QTextBlockUserData):

    def __init__(self):
        QTextBlockUserData.__init__(self)
        self.tags = []
        self.attributes = []
        self.non_tag_structures = []
        self.state = State()
        self.css_user_data = None
        self.doc_name = None

    def clear(self, state=None, doc_name=None):
        self.tags, self.attributes, self.non_tag_structures = [], [], []
        self.state = State() if state is None else state
        self.doc_name = doc_name

    @classmethod
    def tag_ok_for_spell(cls, name):
        return name not in html_spell_tags


class XMLUserData(HTMLUserData):

    @classmethod
    def tag_ok_for_spell(cls, name):
        return name in xml_spell_tags


def add_tag_data(user_data, tag):
    user_data.tags.append(tag)


ATTR_NAME, ATTR_VALUE, ATTR_START, ATTR_END = object(), object(), object(), object()


def add_attr_data(user_data, data_type, data, offset):
    user_data.attributes.append(Attr(offset, data_type, data))


def css(state, text, i, formats, user_data):
    ' Inside a <style> tag '
    pat = cdata_close_pats['style']
    m = pat.search(text, i)
    if m is None:
        css_text = text[i:]
    else:
        css_text = text[i:m.start()]
    ans = []
    css_user_data = user_data.css_user_data = user_data.css_user_data or CSSUserData()
    state.sub_parser_state = css_user_data.state = state.sub_parser_state or CSSState()
    for j, num, fmt in run_loop(css_user_data, css_state_map, formats['css_sub_formats'], css_text):
        ans.append((num, fmt))
    if m is not None:
        state.sub_parser_state = None
        state.parse = IN_CLOSING_TAG
        add_tag_data(user_data, TagStart(m.start(), '', 'style', True, True))
        ans.extend([(2, formats['end_tag']), (len(m.group()) - 2, formats['tag_name'])])
    return ans


def cdata(state, text, i, formats, user_data):
    'CDATA inside tags like <title> or <style>'
    name = state.tags[-1].name
    pat = cdata_close_pats[name]
    m = pat.search(text, i)
    fmt = formats['title' if name == 'title' else 'special']
    if m is None:
        return [(len(text) - i, fmt)]
    state.parse = IN_CLOSING_TAG
    num = m.start() - i
    add_tag_data(user_data, TagStart(m.start(), '', name, True, True))
    return [(num, fmt), (2, formats['end_tag']), (len(m.group()) - 2, formats['tag_name'])]


def process_text(state, text, nbsp_format, spell_format, user_data):
    ans = []
    fmt = None
    if state.is_bold or state.is_italic:
        fmt = syntax_text_char_format()
        if state.is_bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if state.is_italic:
            fmt.setFontItalic(True)
    last = 0
    for m in nbsp_pat.finditer(text):
        ans.extend([(m.start() - last, fmt), (m.end() - m.start(), nbsp_format)])
        last = m.end()
    if not ans:
        ans = [(len(text), fmt)]
    elif last < len(text):
        ans.append((len(text) - last, fmt))

    if do_spell_check and state.tags and user_data.tag_ok_for_spell(state.tags[-1].name):
        split_ans = []
        locale = state.current_lang or dictionaries.default_locale
        sfmt = QTextCharFormat(spell_format)
        if fmt is not None:
            sfmt.merge(fmt)

        tpos = 0
        for tlen, fmt in ans:
            if fmt is nbsp_format:
                split_ans.append((tlen, fmt))
            else:
                split_ans.extend(check_spelling(text[tpos:tpos+tlen], tlen, fmt, locale, sfmt, store_locale.enabled))

            tpos += tlen
        ans = split_ans

    return ans


def normal(state, text, i, formats, user_data):
    ' The normal state in between tags '
    ch = text[i]
    if ch == '<':
        if text[i:i+4] == '<!--':
            state.parse, fmt = IN_COMMENT, formats['comment']
            user_data.non_tag_structures.append(NonTagBoundary(i, True, IN_COMMENT))
            return [(4, fmt)]

        if text[i:i+2] == '<?':
            state.parse, fmt = IN_PI, formats['preproc']
            user_data.non_tag_structures.append(NonTagBoundary(i, True, IN_PI))
            return [(2, fmt)]

        if text[i:i+2] == '<!' and text[i+2:].lstrip().lower().startswith('doctype'):
            state.parse, fmt = IN_DOCTYPE, formats['preproc']
            user_data.non_tag_structures.append(NonTagBoundary(i, True, IN_DOCTYPE))
            return [(2, fmt)]

        m = tag_name_pat.match(text, i + 1)
        if m is None:
            return [(1, formats['<'])]

        tname = m.group()
        closing = tname.startswith('/')
        if closing:
            tname = tname[1:]
        if ':' in tname:
            prefix, name = tname.split(':', 1)
        else:
            prefix, name = '', tname
        if prefix and not name:
            return [(len(m.group()) + 1, formats['only-prefix'])]
        ans = [(2 if closing else 1, formats['end_tag' if closing else 'tag'])]
        if prefix:
            ans.append((len(prefix)+1, formats['nsprefix']))
        ans.append((len(name), formats['tag_name']))
        state.parse = IN_CLOSING_TAG if closing else IN_OPENING_TAG
        add_tag_data(user_data, TagStart(i, prefix, name, closing, True))
        if closing:
            close_tag(state, name)
        else:
            state.tag_being_defined = Tag(name)
        return ans

    if ch == '&':
        m = entity_pat.match(text, i)
        if m is None:
            return [(1, formats['&'])]
        return [(len(m.group()), formats['entity'])]

    if ch == '>':
        return [(1, formats['>'])]

    t = normal_pat.search(text, i).group()
    return process_text(state, t, formats['nbsp'], formats['spell'], user_data)


def opening_tag(cdata_tags, state, text, i, formats, user_data):
    'An opening tag, like <a>'
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch == '/':
        m = self_closing_pat.match(text, i)
        if m is None:
            return [(1, formats['/'])]
        state.parse = NORMAL
        l = len(m.group())
        add_tag_data(user_data, TagEnd(i + l - 1, True, False))
        return [(l, formats['tag'])]
    if ch == '>':
        finish_opening_tag(state, cdata_tags)
        add_tag_data(user_data, TagEnd(i, False, False))
        return [(1, formats['tag'])]
    m = attribute_name_pat.match(text, i)
    if m is None:
        return [(1, formats['?'])]
    state.parse = ATTRIBUTE_NAME
    attrname = state.attribute_name = m.group()
    add_attr_data(user_data, ATTR_NAME, attrname, m.start())
    prefix, name = attrname.partition(':')[0::2]
    if not prefix and not name:
        return [(len(attrname), formats['?'])]
    if prefix and name:
        return [(len(prefix) + 1, formats['nsprefix']), (len(name), formats['attr'])]
    return [(len(prefix), formats['attr'])]


def attribute_name(state, text, i, formats, user_data):
    ' After attribute name '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch == '=':
        state.parse = ATTRIBUTE_VALUE
        return [(1, formats['attr'])]
    # Standalone attribute with no value
    state.parse = IN_OPENING_TAG
    state.attribute_name = None
    return [(0, None)]


def attribute_value(state, text, i, formats, user_data):
    ' After attribute = '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch in {'"', "'"}:
        state.parse = SQ_VAL if ch == "'" else DQ_VAL
        return [(1, formats['string'])]
    state.parse = IN_OPENING_TAG
    state.attribute_name = None
    m = unquoted_val_pat.match(text, i)
    if m is None:
        return [(1, formats['no-attr-value'])]
    return [(len(m.group()), formats['string'])]


def quoted_val(state, text, i, formats, user_data):
    ' A quoted attribute value '
    quote = '"' if state.parse is DQ_VAL else "'"
    add_attr_data(user_data, ATTR_VALUE, ATTR_START, i)
    pos = text.find(quote, i)
    if pos == -1:
        num = len(text) - i
        is_link = is_class = False
    else:
        num = pos - i + 1
        state.parse = IN_OPENING_TAG
        if state.tag_being_defined is not None and state.attribute_name in ('lang', 'xml:lang'):
            try:
                state.tag_being_defined.lang = parse_lang_code(text[i:pos])
            except ValueError:
                pass
        add_attr_data(user_data, ATTR_VALUE, ATTR_END, i + num)
        is_link = state.attribute_name in LINK_ATTRS
        is_class = not is_link and state.attribute_name == 'class'

    if is_link:
        if verify_link(text[i:i+num - 1], user_data.doc_name) is False:
            return [(num - 1, formats['bad_link']), (1, formats['string'])]
        return [(num - 1, formats['link']), (1, formats['string'])]
    elif is_class:
        return [(num - 1, formats['class_attr']), (1, formats['string'])]
    return [(num, formats['string'])]


def closing_tag(state, text, i, formats, user_data):
    ' A closing tag like </a> '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    pos = text.find('>', i)
    if pos == -1:
        return [(len(text) - i, formats['bad-closing'])]
    state.parse = NORMAL
    num = pos - i + 1
    ans = [(1, formats['end_tag'])]
    if num > 1:
        ans.insert(0, (num - 1, formats['bad-closing']))
    add_tag_data(user_data, TagEnd(pos, False, False))
    return ans


def in_comment(state, text, i, formats, user_data):
    ' Comment, processing instruction or doctype '
    end = {IN_COMMENT:'-->', IN_PI:'?>'}.get(state.parse, '>')
    pos = text.find(end, i)
    fmt = formats['comment' if state.parse is IN_COMMENT else 'preproc']
    if pos == -1:
        num = len(text) - i
    else:
        user_data.non_tag_structures.append(NonTagBoundary(pos, False, state.parse))
        num = pos - i + len(end)
        state.parse = NORMAL
    return [(num, fmt)]


state_map = {
    NORMAL:normal,
    IN_OPENING_TAG: partial(opening_tag, cdata_tags),
    IN_CLOSING_TAG: closing_tag,
    ATTRIBUTE_NAME: attribute_name,
    ATTRIBUTE_VALUE: attribute_value,
    CDATA: cdata,
    CSS: css,
}

for x in (IN_COMMENT, IN_PI, IN_DOCTYPE):
    state_map[x] = in_comment

for x in (SQ_VAL, DQ_VAL):
    state_map[x] = quoted_val

xml_state_map = state_map.copy()
xml_state_map[IN_OPENING_TAG] = partial(opening_tag, set())


def create_formats(highlighter, add_css=True):
    t = highlighter.theme
    formats = {
        'tag': t['Function'],
        'end_tag': t['Function'],
        'attr': t['Type'],
        'entity': t['Special'],
        'error': t['Error'],
        'comment': t['Comment'],
        'special': t['Special'],
        'string': t['String'],
        'nsprefix': t['Constant'],
        'preproc': t['PreProc'],
        'nbsp': t['SpecialCharacter'],
        'spell': t['SpellError'],
    }
    for name, msg in iteritems({
            '<': _('An unescaped < is not allowed. Replace it with &lt;'),
            '&': _('An unescaped ampersand is not allowed. Replace it with &amp;'),
            '>': _('An unescaped > is not allowed. Replace it with &gt;'),
            '/': _('/ not allowed except at the end of the tag'),
            '?': _('Unknown character'),
            'bad-closing': _('A closing tag must contain only the tag name and nothing else'),
            'no-attr-value': _('Expecting an attribute value'),
            'only-prefix': _('A tag name cannot end with a colon'),
    }):
        f = formats[name] = syntax_text_char_format(formats['error'])
        f.setToolTip(msg)
    f = formats['title'] = syntax_text_char_format()
    f.setFontWeight(QFont.Weight.Bold)
    if add_css:
        formats['css_sub_formats'] = create_css_formats(highlighter)
    formats['spell'].setProperty(SPELL_PROPERTY, True)
    formats['class_attr'] = syntax_text_char_format(t['Special'])
    formats['class_attr'].setProperty(CLASS_ATTRIBUTE_PROPERTY, True)
    formats['class_attr'].setToolTip(_('Hold down the Ctrl key and click to open the first matching CSS style rule'))
    formats['link'] = syntax_text_char_format(t['Link'])
    formats['link'].setProperty(LINK_PROPERTY, True)
    formats['link'].setToolTip(_('Hold down the Ctrl key and click to open this link'))
    formats['bad_link'] = syntax_text_char_format(t['BadLink'])
    formats['bad_link'].setProperty(LINK_PROPERTY, True)
    formats['bad_link'].setToolTip(_('This link points to a file that is not present in the book'))
    formats['tag_name'] = f = syntax_text_char_format(t['Statement'])
    f.setProperty(TAG_NAME_PROPERTY, True)
    return formats


class Highlighter(SyntaxHighlighter):

    state_map = state_map
    create_formats_func = create_formats
    spell_attributes = ('alt', 'title')
    user_data_factory = HTMLUserData

    def tag_ok_for_spell(self, name):
        return HTMLUserData.tag_ok_for_spell(name)


class XMLHighlighter(Highlighter):

    state_map = xml_state_map
    spell_attributes = ('opf:file-as',)
    user_data_factory = XMLUserData

    def create_formats_func(self):
        return create_formats(self, add_css=False)

    def tag_ok_for_spell(self, name):
        return XMLUserData.tag_ok_for_spell(name)


def profile():
    import sys
    from qt.core import QTextDocument

    from calibre.gui2 import Application
    from calibre.gui2.tweak_book import set_book_locale
    from calibre.gui2.tweak_book.editor.themes import get_theme
    app = Application([])
    set_book_locale('en')
    with open(sys.argv[-2], 'rb') as f:
        raw = f.read().decode('utf-8')
    doc = QTextDocument()
    doc.setPlainText(raw)
    h = Highlighter()
    theme = get_theme(tprefs['editor_theme'])
    h.apply_theme(theme)
    h.set_document(doc)
    h.join()
    import cProfile
    print('Running profile on', sys.argv[-2])
    h.rehighlight()
    cProfile.runctx('h.join()', {}, {'h':h}, sys.argv[-1])
    print('Stats saved to:', sys.argv[-1])
    del h
    del doc
    del app


if __name__ == '__main__':
    from calibre.gui2.tweak_book.editor.widget import launch_editor
    launch_editor('''\
<!DOCTYPE html>
<html xml:lang="en" lang="en">
<!--
-->
    <head>
        <meta charset="utf-8" />
        <title>A title with a tag <span> in it, the tag is treated as normal text</title>
        <style type="text/css">
            body {
                  color: green;
                  font-size: 12pt;
            }
        </style>
        <style type="text/css">p.small { font-size: x-small; color:gray }</style>
    </head id="invalid attribute on closing tag">
    <body lang="en_IN"><p:
        <!-- The start of the actual body text -->
        <h1 lang="en_US">A heading that should appear in bold, with an <i>italic</i> word</h1>
        <p>Some text with inline formatting, that is syntax highlighted. A <b>bold</b> word, and an <em>italic</em> word. \
<i>Some italic text with a <b>bold-italic</b> word in </i>the middle.</p>
        <!-- Let's see what exotic constructs like namespace prefixes and empty attributes look like -->
        <svg:svg xmlns:svg="http://whatever" />
        <input disabled><input disabled /><span attr=<></span>
        <!-- Non-breaking spaces are rendered differently from normal spaces, so that they stand out -->
        <p>Some\xa0words\xa0separated\xa0by\xa0non\u2011breaking\xa0spaces and non\u2011breaking hyphens.</p>
        <p>Some non-BMP unicode text:\U0001f431\U0001f431\U0001f431</p>
    </body>
</html>
''', path_is_raw=True)
