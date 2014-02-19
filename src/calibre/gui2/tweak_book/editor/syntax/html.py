#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from functools import partial
from collections import namedtuple

from PyQt4.Qt import QFont, QTextBlockUserData

from calibre.gui2.tweak_book.editor import SyntaxTextCharFormat
from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter, run_loop
from calibre.gui2.tweak_book.editor.syntax.css import create_formats as create_css_formats, state_map as css_state_map, State as CSSState

from html5lib.constants import cdataElements, rcdataElements

cdata_tags = cdataElements | rcdataElements
bold_tags = {'b', 'strong'} | {'h%d' % d for d in range(1, 7)}
italic_tags = {'i', 'em'}
normal_pat = re.compile(r'[^<>&]+')
entity_pat = re.compile(r'&#{0,1}[a-zA-Z0-9]{1,8};')
tag_name_pat = re.compile(r'/{0,1}[a-zA-Z0-9:]+')
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

class Tag(object):

    __slots__ = ('name', 'bold', 'italic', 'lang', 'hash')

    def __init__(self, name, bold=None, italic=None):
        self.name = name
        self.bold = name in bold_tags if bold is None else bold
        self.italic = name in italic_tags if italic is None else italic
        self.lang = None
        self.hash = 0

    def __hash__(self):
        return self.hash

    def __eq__(self, other):
        return self.name == getattr(other, 'name', None) and self.lang == getattr(other, 'lang', False)

    def copy(self):
        ans = Tag(self.name, self.bold, self.italic)
        ans.lang, ans.hash = self.lang, self.hash
        return ans

    def update_hash(self):
        self.hash = hash((self.name, self.lang))

class State(object):

    __slots__ = ('tag_being_defined', 'tags', 'is_bold', 'is_italic',
                 'current_lang', 'parse', 'get_user_data', 'set_user_data',
                 'css_formats', 'stack', 'sub_parser_state', 'default_lang')

    def __init__(self):
        self.tags = []
        self.is_bold = self.is_italic = False
        self.tag_being_defined = self.current_lang = self.get_user_data = self.set_user_data = \
            self.css_formats = self.stack = self.sub_parser_state = self.default_lang = None
        self.parse = NORMAL

    def copy(self):
        ans = State()
        for x in self.__slots__:
            setattr(ans, x, getattr(self, x))
        self.tags = [x.copy() for x in self.tags]
        if self.tag_being_defined is not None:
            self.tag_being_defined = self.tag_being_defined.copy()
        return ans

    @property
    def value(self):
        if self.tag_being_defined is not None:
            self.tag_being_defined.update_hash()
        return self.stack.index_for(self)

    def __hash__(self):
        return hash((self.parse, self.sub_parser_state, self.tag_being_defined, tuple(self.tags)))

    def __eq__(self, other):
        return (
            self.parse == getattr(other, 'parse', -1) and
            self.sub_parser_state == getattr(other, 'sub_parser_state', -1) and
            self.tag_being_defined == getattr(other, 'tag_being_defined', False) and
            self.tags == getattr(other, 'tags', None)
        )

    def open_tag(self, name):
        self.tag_being_defined = Tag(name)

    def close_tag(self, name):
        removed_tags = []
        for tag in reversed(self.tags):
            removed_tags.append(tag)
            if tag.name == name:
                break
        else:
            return  # No matching open tag found, ignore the closing tag
        # Remove all tags upto the matching open tag
        self.tags = self.tags[:-len(removed_tags)]
        self.sub_parser_state = 0
        # Check if we should still be bold or italic
        if self.is_bold:
            self.is_bold = False
            for tag in reversed(self.tags):
                if tag.bold:
                    self.is_bold = True
                    break
        if self.is_italic:
            self.is_italic = False
            for tag in reversed(self.tags):
                if tag.italic:
                    self.is_italic = True
                    break
        # Set the current language to the first lang attribute in a still open tag
        self.current_lang = None
        for tag in reversed(self.tags):
            if tag.lang is not None:
                self.current_lang = tag.lang
                break

    def finish_opening_tag(self, cdata_tags):
        self.parse = NORMAL
        if self.tag_being_defined is None:
            return
        t, self.tag_being_defined = self.tag_being_defined, None
        t.update_hash()
        self.tags.append(t)
        self.is_bold = self.is_bold or t.bold
        self.is_italic = self.is_italic or t.italic
        self.current_lang = t.lang or self.current_lang
        if t.name in cdata_tags:
            self.parse = CSS if t.name == 'style' else CDATA
            self.sub_parser_state = 0

    def __repr__(self):
        return '<State %s is_bold=%s is_italic=%s current_lang=%s>' % (
            '->'.join(x.name for x in self.tags), self.is_bold, self.is_italic, self.current_lang)
    __str__ = __repr__

class Stack(object):

    ''' Maintain an efficient bi-directional mapping between states and index
    numbers. Ensures that if state1 == state2 then their corresponding index
    numbers are the same and vice versa. This is need so that the state number
    passed to Qt does not change unless the underlying state has actually
    changed. '''

    def __init__(self):
        self.index_map = []
        self.state_map = {}

    def index_for(self, state):
        ans = self.state_map.get(state, None)
        if ans is None:
            self.state_map[state] = ans = len(self.index_map)
            self.index_map.append(state)
        return ans

    def state_for(self, index):
        try:
            return self.index_map[index]
        except IndexError:
            return None

class HTMLUserData(QTextBlockUserData):

    def __init__(self):
        QTextBlockUserData.__init__(self)
        self.tags = []

def add_tag_data(state, tag):
    ud = q = state.get_user_data()
    if ud is None:
        ud = HTMLUserData()
    ud.tags.append(tag)
    if q is None:
        state.set_user_data(ud)

def css(state, text, i, formats):
    ' Inside a <style> tag '
    pat = cdata_close_pats['style']
    m = pat.search(text, i)
    if m is None:
        css_text = text[i:]
    else:
        css_text = text[i:m.start()]
    ans = []
    css_state = CSSState(state.sub_parser_state)
    for j, num, fmt in run_loop(css_state, css_state_map, state.css_formats, css_text):
        ans.append((num, fmt))
    state.sub_parser_state = css_state.value
    if m is not None:
        state.sub_parser_state = 0
        state.parse = IN_CLOSING_TAG
        add_tag_data(state, TagStart(m.start(), 'style', '', True, True))
        ans.extend([(2, formats['end_tag']), (len(m.group()) - 2, formats['tag_name'])])
    return ans

def cdata(state, text, i, formats):
    'CDATA inside tags like <title> or <style>'
    name = state.tags[-1].name
    pat = cdata_close_pats[name]
    m = pat.search(text, i)
    fmt = formats['title' if name == 'title' else 'special']
    if m is None:
        return [(len(text) - i, fmt)]
    state.parse = IN_CLOSING_TAG
    num = m.start() - i
    add_tag_data(state, TagStart(m.start(), name, '', True, True))
    return [(num, fmt), (2, formats['end_tag']), (len(m.group()) - 2, formats['tag_name'])]

def mark_nbsp(state, text, nbsp_format):
    ans = []
    fmt = None
    if state.is_bold or state.is_italic:
        fmt = SyntaxTextCharFormat()
        if state.is_bold:
            fmt.setFontWeight(QFont.Bold)
        if state.is_italic:
            fmt.setFontItalic(True)
    last = 0
    for m in nbsp_pat.finditer(text):
        ans.extend([(m.start() - last, fmt), (m.end() - m.start(), nbsp_format)])
        last = m.end()
    if not ans:
        ans = [(len(text), fmt)]
    return ans

def normal(state, text, i, formats):
    ' The normal state in between tags '
    ch = text[i]
    if ch == '<':
        if text[i:i+4] == '<!--':
            state.parse, fmt = IN_COMMENT, formats['comment']
            return [(4, fmt)]

        if text[i:i+2] == '<?':
            state.parse, fmt = IN_PI, formats['preproc']
            return [(2, fmt)]

        if text[i:i+2] == '<!' and text[i+2:].lstrip().lower().startswith('doctype'):
            state.parse, fmt = IN_DOCTYPE, formats['preproc']
            return [(2, fmt)]

        m = tag_name_pat.match(text, i + 1)
        if m is None:
            return [(1, formats['<'])]

        name = m.group()
        closing = name.startswith('/')
        state.parse = IN_CLOSING_TAG if closing else IN_OPENING_TAG
        ans = [(2 if closing else 1, formats['end_tag' if closing else 'tag'])]
        if closing:
            name = name[1:]
        prefix, name = name.partition(':')[0::2]
        if prefix and name:
            ans.append((len(prefix)+1, formats['nsprefix']))
        ans.append((len(name or prefix), formats['tag_name']))
        add_tag_data(state, TagStart(i, prefix, name, closing, True))
        (state.close_tag if closing else state.open_tag)(name or prefix)
        return ans

    if ch == '&':
        m = entity_pat.match(text, i)
        if m is None:
            return [(1, formats['&'])]
        return [(len(m.group()), formats['entity'])]

    if ch == '>':
        return [(1, formats['>'])]

    t = normal_pat.search(text, i).group()
    return mark_nbsp(state, t, formats['nbsp'])

def opening_tag(cdata_tags, state, text, i, formats):
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
        add_tag_data(state, TagEnd(i + l - 1, True, False))
        return [(l, formats['tag'])]
    if ch == '>':
        state.finish_opening_tag(cdata_tags)
        add_tag_data(state, TagEnd(i, False, False))
        return [(1, formats['tag'])]
    m = attribute_name_pat.match(text, i)
    if m is None:
        return [(1, formats['?'])]
    state.parse = ATTRIBUTE_NAME
    prefix, name = m.group().partition(':')[0::2]
    if prefix and name:
        return [(len(prefix) + 1, formats['nsprefix']), (len(name), formats['attr'])]
    return [(len(prefix), formats['attr'])]

def attribute_name(state, text, i, formats):
    ' After attribute name '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch == '=':
        state.parse = ATTRIBUTE_VALUE
        return [(1, formats['attr'])]
    state.parse = IN_OPENING_TAG
    if ch in {'>', '/'}:
        # Standalone attribute with no value
        return [(0, None)]
    return [(1, formats['no-attr-value'])]

def attribute_value(state, text, i, formats):
    ' After attribute = '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch in {'"', "'"}:
        state.parse = SQ_VAL if ch == "'" else DQ_VAL
        return [(1, formats['string'])]
    state.parse = IN_OPENING_TAG
    m = unquoted_val_pat.match(text, i)
    if m is None:
        return [(1, formats['no-attr-value'])]
    return [(len(m.group()), formats['string'])]

def quoted_val(state, text, i, formats):
    ' A quoted attribute value '
    quote = '"' if state.parse is DQ_VAL else "'"
    pos = text.find(quote, i)
    if pos == -1:
        num = len(text) - i
    else:
        num = pos - i + 1
        state.parse = IN_OPENING_TAG
    return [(num, formats['string'])]

def closing_tag(state, text, i, formats):
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
    add_tag_data(state, TagEnd(pos, False, False))
    return ans

def in_comment(state, text, i, formats):
    ' Comment, processing instruction or doctype '
    end = {IN_COMMENT:'-->', IN_PI:'?>'}.get(state.parse, '>')
    pos = text.find(end, i)
    fmt = formats['comment' if state.parse is IN_COMMENT else 'preproc']
    if pos == -1:
        num = len(text) - i
    else:
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

def create_formats(highlighter):
    t = highlighter.theme
    formats = {
        'tag': t['Function'],
        'end_tag': t['Function'],
        'attr': t['Type'],
        'tag_name' : t['Statement'],
        'entity': t['Special'],
        'error': t['Error'],
        'comment': t['Comment'],
        'special': t['Special'],
        'string': t['String'],
        'nsprefix': t['Constant'],
        'preproc': t['PreProc'],
        'nbsp': t['SpecialCharacter'],
    }
    for name, msg in {
        '<': _('An unescaped < is not allowed. Replace it with &lt;'),
        '&': _('An unescaped ampersand is not allowed. Replace it with &amp;'),
        '>': _('An unescaped > is not allowed. Replace it with &gt;'),
        '/': _('/ not allowed except at the end of the tag'),
        '?': _('Unknown character'),
        'bad-closing': _('A closing tag must contain only the tag name and nothing else'),
        'no-attr-value': _('Expecting an attribute value'),
    }.iteritems():
        f = formats[name] = SyntaxTextCharFormat(formats['error'])
        f.setToolTip(msg)
    f = formats['title'] = SyntaxTextCharFormat()
    f.setFontWeight(QFont.Bold)
    return formats


class HTMLHighlighter(SyntaxHighlighter):

    state_map = state_map
    create_formats_func = create_formats

    def create_formats(self):
        super(HTMLHighlighter, self).create_formats()
        self.default_state = State()
        self.default_state.css_formats = create_css_formats(self)
        self.default_state.stack = Stack()

    def create_state(self, val):
        if val < 0:
            return self.default_state.copy()
        ans = self.default_state.stack.state_for(val) or self.default_state
        return ans.copy()

class XMLHighlighter(HTMLHighlighter):

    state_map = xml_state_map

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
    <body>
        <!-- The start of the actual body text -->
        <h1>A heading that should appear in bold, with an <i>italic</i> word</h1>
        <p>Some text with inline formatting, that is syntax highlighted. A <b>bold</b> word, and an <em>italic</em> word. \
<i>Some italic text with a <b>bold-italic</b> word in </i>the middle.</p>
        <!-- Let's see what exotic constructs like namespace prefixes and empty attributes look like -->
        <svg:svg xmlns:svg="http://whatever" />
        <input disabled><input disabled /><span attr=<></span>
        <!-- Non-breaking spaces are rendered differently from normal spaces, so that they stand out -->
        <p>Some\xa0words\xa0separated\xa0by\xa0non\u2011breaking\xa0spaces and non\u2011breaking hyphens.</p>
    </body>
</html>
''', path_is_raw=True)
