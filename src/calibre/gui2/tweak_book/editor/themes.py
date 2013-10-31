#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

from PyQt4.Qt import (QColor, QTextCharFormat, QBrush, QFont)

underline_styles = {'single', 'dash', 'dot', 'dash_dot', 'dash_dot_dot', 'wave', 'spell'}

DEFAULT_THEME = 'calibre-dark'

THEMES = {
    'calibre-dark':  # {{{  Based on the wombat color scheme for vim
    '''
    CursorLine   bg=2d2d2d
    CursorColumn bg=2d2d2d
    ColorColumn  bg=2d2d2d
    MatchParen   fg=f6f3e8 bg=857b6f bold
    Pmenu        fg=f6f3e8 bg=444444
    PmenuSel     fg=yellow bg=cae682
    Tooltip      fg=black bg=ffffed

    Cursor       bg=656565
    Normal       fg=f6f3e8 bg=242424
    LineNr       fg=857b6f bg=000000
    LineNrC      fg=yellow
    Visual       fg=f6f3e8 bg=444444

    Comment      fg=99968b
    Todo         fg=8f8f8f
    String       fg=95e454
    Identifier   fg=cae682
    Function     fg=cae682
    Type         fg=cae682
    Statement    fg=8ac6f2
    Keyword      fg=8ac6f2
    Constant     fg=e5786d
    PreProc      fg=e5786d
    Number       fg=e5786d
    Special      fg=e7f6da
    Error        us=wave uc=red

    ''',  # }}}

}

def read_color(col):
    if QColor.isValidColor(col):
        return QBrush(QColor(col))
    try:
        r, g, b = col[0:2], col[2:4], col[4:6]
        r, g, b = int(r, 16), int(g, 16), int(b, 16)
        return QBrush(QColor(r, g, b))
    except Exception:
        pass

Highlight = namedtuple('Highlight', 'fg bg bold italic underline underline_color')

def read_theme(raw):
    ans = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        bold = italic = False
        fg = bg = name = underline = underline_color = None
        line = line.partition('#')[0]
        for i, token in enumerate(line.split()):
            if i == 0:
                name = token
            else:
                if token == 'bold':
                    bold = True
                elif token == 'italic':
                    italic = True
                elif '=' in token:
                    prefix, val = token.partition('=')[0::2]
                    if prefix == 'us':
                        underline = val if val in underline_styles else None
                    elif prefix == 'uc':
                        underline_color = read_color(val)
                    elif prefix == 'fg':
                        fg = read_color(val)
                    elif prefix == 'bg':
                        bg = read_color(val)
        if name is not None:
            ans[name] = Highlight(fg, bg, bold, italic, underline, underline_color)
    return ans


THEMES = {k:read_theme(raw) for k, raw in THEMES.iteritems()}

def u(x):
    x = {'spell':'SpellCheck', 'dash_dot':'DashDot', 'dash_dot_dot':'DashDotDot'}.get(x, x.capitalize())
    if 'Dot' in x:
        return x + 'Line'
    return x + 'Underline'
underline_styles = {x:getattr(QTextCharFormat, u(x)) for x in underline_styles}

def highlight_to_char_format(h):
    ans = QTextCharFormat()
    if h.bold:
        ans.setFontWeight(QFont.Bold)
    if h.italic:
        ans.setFontItalic(True)
    if h.fg is not None:
        ans.setForeground(h.fg)
    if h.bg is not None:
        ans.setBackground(h.bg)
    if h.underline is not None:
        ans.setUnderlineStyle(underline_styles[h.underline])
        if h.underline_color is not None:
            ans.setUnderlineColor(h.underline_color.color())
    return ans

def theme_color(theme, name, attr):
    try:
        return getattr(theme[name], attr).color()
    except (KeyError, AttributeError):
        return getattr(THEMES[DEFAULT_THEME], attr).color()

