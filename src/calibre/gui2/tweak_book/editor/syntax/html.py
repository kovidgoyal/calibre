#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re

from PyQt4.Qt import (QTextCharFormat, QFont)

from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from html5lib.constants import cdataElements, rcdataElements

cdata_tags = cdataElements | rcdataElements
bold_tags = {'b', 'strong'} | {'h%d' % d for d in range(1, 7)}
italic_tags = {'i', 'em'}
normal_pat = re.compile(r'[^<>&]')
entity_pat = re.compile(r'&#{0,1}[a-zA-Z0-9]{1,8};')
tag_name_pat = re.compile(r'/{0,1}[a-zA-Z0-9:]+')
space_chars = ' \t\r\n\u000c'
attribute_name_pat = re.compile(r'''[^%s"'/><=]+''' % space_chars)
self_closing_pat = re.compile(r'/\s*>')
unquoted_val_pat = re.compile(r'''[^%s'"=<>`]+''' % space_chars)
cdata_close_pats = {x:re.compile(r'</%s' % x, flags=re.I) for x in cdata_tags}

class State(object):

    ''' Store the parsing state, a stack of bold and italic formatting and the
    last seen open tag, all in a single integer, so that it can be used with.
    This assumes an int is at least 32 bits.'''

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

    TAGS = {x:i+1 for i, x in enumerate(cdata_tags | bold_tags | italic_tags)}
    TAGS_RMAP = {v:k for k, v in TAGS.iteritems()}
    UNKNOWN_TAG = '___'

    def __init__(self, num):
        self.parse  = num & 0b1111
        self.bold   = (num >> 4) & 0b11111111
        self.italic = (num >> 12) & 0b11111111
        self.tag    = self.TAGS_RMAP.get(num >> 20, self.UNKNOWN_TAG)

    @property
    def value(self):
        tag = self.TAGS.get(self.tag.lower(), 0)
        return ((self.parse & 0b1111) |
                ((max(0, self.bold) & 0b11111111) << 4) |
                ((max(0, self.italic) & 0b11111111) << 12) |
                (tag << 20))

def cdata(state, text, i, formats):
    'CDATA inside tags like <title> or <style>'
    pat = cdata_close_pats[state.tag]
    m = pat.search(text, i)
    fmt = formats['title' if state.tag == 'title' else 'special']
    if m is None:
        return [(len(text) - i, fmt)]
    state.parse = State.IN_CLOSING_TAG
    num = m.start() - i
    return [(num, fmt), (2, formats['end_tag']), (len(m.group()) - 2, formats['tag_name'])]

def normal(state, text, i, formats):
    ' The normal state in between tags '
    ch = text[i]
    if ch == '<':
        if text[i:i+4] == '<!--':
            state.parse, fmt = state.IN_COMMENT, formats['comment']
            return [(4, fmt)]

        if text[i:i+2] == '<?':
            state.parse, fmt = state.IN_PI, formats['preproc']
            return [(2, fmt)]

        if text[i:i+2] == '<!' and text[i+2:].lstrip().lower().startswith('doctype'):
            state.parse, fmt = state.IN_DOCTYPE, formats['preproc']
            return [(2, fmt)]

        m = tag_name_pat.match(text, i + 1)
        if m is None:
            return [(1, formats['<'])]

        name = m.group()
        closing = name.startswith('/')
        state.parse = state.IN_CLOSING_TAG if closing else state.IN_OPENING_TAG
        ans = [(2 if closing else 1, formats['end_tag' if closing else 'tag'])]
        if closing:
            name = name[1:]
        prefix, name = name.partition(':')[0::2]
        state.tag = name or prefix
        if prefix and name:
            ans.append((len(prefix)+1, formats['nsprefix']))
        ans.append((len(name or prefix), formats['tag_name']))
        return ans

    if ch == '&':
        m = entity_pat.match(text, i)
        if m is None:
            return [(1, formats['&'])]
        return [(len(m.group()), formats['entity'])]

    if ch == '>':
        return [(1, formats['>'])]

    t = normal_pat.search(text, i).group()
    fmt = None
    if state.bold or state.italic:
        fmt = QTextCharFormat()
        if state.bold:
            fmt.setFontWeight(QFont.Bold)
        if state.italic:
            fmt.setFontItalic(True)
    return [(len(t), fmt)]

def opening_tag(state, text, i, formats):
    'An opening tag, like <a>'
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    if ch == '/':
        m = self_closing_pat.match(text, i)
        if m is None:
            return [(1, formats['/'])]
        state.parse = state.NORMAL
        state.tag = State.UNKNOWN_TAG
        return [(len(m.group()), formats['tag'])]
    if ch == '>':
        state.parse = state.NORMAL
        tag = state.tag.lower()
        if tag in cdata_tags:
            state.parse = state.CDATA
        state.bold += int(tag in bold_tags)
        state.italic += int(tag in italic_tags)
        return [(1, formats['tag'])]
    m = attribute_name_pat.match(text, i)
    if m is None:
        return [(1, formats['?'])]
    state.parse = state.ATTRIBUTE_NAME
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
        state.parse = State.ATTRIBUTE_VALUE
        return [(1, formats['attr'])]
    state.parse = State.IN_OPENING_TAG
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
        state.parse = State.SQ_VAL if ch == "'" else State.DQ_VAL
        return [(1, formats['string'])]
    state.parse = State.IN_OPENING_TAG
    m = unquoted_val_pat.match(text, i)
    if m is None:
        return [(1, formats['no-attr-value'])]
    return [(len(m.group()), formats['string'])]

def quoted_val(state, text, i, formats):
    ' A quoted attribute value '
    quote = '"' if state.parse == State.DQ_VAL else "'"
    pos = text.find(quote, i)
    if pos == -1:
        num = len(text) - i
    else:
        num = pos - i + 1
        state.parse = State.IN_OPENING_TAG
    return [(num, formats['string'])]

def closing_tag(state, text, i, formats):
    ' A closing tag like </a> '
    ch = text[i]
    if ch in space_chars:
        return [(1, None)]
    pos = text.find('>', i)
    if pos == -1:
        return [(len(text) - i, formats['bad-closing'])]
    state.parse = state.NORMAL
    tag = state.tag.lower()
    state.bold -= int(tag in bold_tags)
    state.italic -= int(tag in italic_tags)
    num = pos - i + 1
    ans = [(1, formats['end_tag'])]
    if num > 1:
        ans.insert(0, (num - 1, formats['bad-closing']))
    state.tag = State.UNKNOWN_TAG
    return ans

def in_comment(state, text, i, formats):
    ' Comment, processing instruction or doctype '
    end = {state.IN_COMMENT:'-->', state.IN_PI:'?>'}.get(state.parse, '>')
    pos = text.find(end, i+1)
    fmt = formats['comment' if state.parse == state.IN_COMMENT else 'preproc']
    if pos == -1:
        num = len(text) - i
    else:
        num = pos - i + len(end)
        state.parse = state.NORMAL
    return [(num, fmt)]

state_map = {
    State.NORMAL:normal,
    State.IN_OPENING_TAG: opening_tag,
    State.IN_CLOSING_TAG: closing_tag,
    State.ATTRIBUTE_NAME: attribute_name,
    State.ATTRIBUTE_VALUE: attribute_value,
    State.CDATA: cdata,
}

for x in (State.IN_COMMENT, State.IN_PI, State.IN_DOCTYPE):
    state_map[x] = in_comment

for x in (State.SQ_VAL, State.DQ_VAL):
    state_map[x] = quoted_val

class HTMLHighlighter(SyntaxHighlighter):

    def __init__(self, parent):
        SyntaxHighlighter.__init__(self, parent)

    def create_formats(self):
        t = self.theme
        self.formats = {
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
            f = self.formats[name] = QTextCharFormat(self.formats['error'])
            f.setToolTip(msg)
        f = self.formats['title'] = QTextCharFormat()
        f.setFontWeight(QFont.Bold)

    def highlightBlock(self, text):
        try:
            self.do_highlight(unicode(text))
        except:
            import traceback
            traceback.print_exc()

    def do_highlight(self, text):
        state = self.previousBlockState()
        if state == -1:
            state = State.NORMAL
        state = State(state)

        i = 0
        while i < len(text):
            fmt = state_map[state.parse](state, text, i, self.formats)
            for num, f in fmt:
                if f is not None:
                    self.setFormat(i, num, f)
                i += num

        self.setCurrentBlockState(state.value)

if __name__ == '__main__':
    from calibre.gui2.tweak_book.editor.text import launch_editor
    launch_editor('''\
<!DOCTYPE html>
<html xml:lang="en" lang="en">
    <head>
        <meta charset="utf-8" />
        <title>A title with a tag <span> in it, the tag is treated as normal text</title>
        <style type="text/css">
            body {
                  color: green;
                  font-size: 12pt;
            }
        </style>
    </head id="invalid attribute on closing tag">
    <body>
        <!-- The start of the actual body text -->
        <h1>A heading that should appear in bold, with an <i>italic</i> word</h1>
        <p>Some text with inline formatting, that is syntax highlighted. A <b>bold</b> word, and an <em>italic</em> word. \
<i>Some italic text with a <b>bold italic</b> word in </i> middle.</p>
        <!-- Let's see what exotic constructs like namespace prefixes and empty attributes look like -->
        <svg:svg xmlns:svg="http://whatever" />
        <input disabled><input disabled /><span attr=<></span>
    </body>
</html>
''')
