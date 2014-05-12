#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import namedtuple

from PyQt4.Qt import (QColor, QBrush, QFont, QApplication, QPalette)

from calibre.gui2.tweak_book.editor import SyntaxTextCharFormat

underline_styles = {'single', 'dash', 'dot', 'dash_dot', 'dash_dot_dot', 'wave', 'spell'}

_default_theme = None
def default_theme():
    global _default_theme
    if _default_theme is None:
        isdark = QApplication.instance().palette().color(QPalette.WindowText).lightness() > 128
        _default_theme = 'wombat-dark' if isdark else 'pyte-light'
    return _default_theme

# The solarized themes {{{
SLDX = {'base03':'1c1c1c', 'base02':'262626', 'base01':'585858', 'base00':'626262', 'base0':'808080', 'base1':'8a8a8a', 'base2':'e4e4e4', 'base3':'ffffd7', 'yellow':'af8700', 'orange':'d75f00', 'red':'d70000', 'magenta':'af005f', 'violet':'5f5faf', 'blue':'0087ff', 'cyan':'00afaf', 'green':'5f8700'}  # noqa
SLD  = {'base03':'002b36', 'base02':'073642', 'base01':'586e75', 'base00':'657b83', 'base0':'839496', 'base1':'93a1a1', 'base2':'eee8d5', 'base3':'fdf6e3', 'yellow':'b58900', 'orange':'cb4b16', 'red':'dc322f', 'magenta':'d33682', 'violet':'6c71c4', 'blue':'268bd2', 'cyan':'2aa198', 'green':'859900'}  # noqa
m = {'base%d'%n:'base%02d'%n for n in xrange(1, 4)}
m.update({'base%02d'%n:'base%d'%n for n in xrange(1, 4)})
SLL = {m.get(k, k) : v for k, v in SLD.iteritems()}
SLLX = {m.get(k, k) : v for k, v in SLDX.iteritems()}
SOLARIZED = \
    '''
    CursorLine   bg={base02}
    CursorColumn bg={base02}
    ColorColumn  bg={base02}
    HighlightRegion bg={base00}
    MatchParen   bg={base02} fg={magenta}
    Pmenu        fg={base0} bg={base02}
    PmenuSel     fg={base01} bg={base2}

    Cursor       fg={base03} bg={base0}
    Normal       fg={base0} bg={base03}
    LineNr       fg={base01} bg={base02}
    LineNrC      fg={magenta}
    Visual       fg={base01} bg={base03}

    Comment      fg={base01} italic
    Todo         fg={magenta} bold
    String       fg={cyan}
    Constant     fg={cyan}
    Number       fg={cyan}
    PreProc      fg={orange}
    Identifier   fg={blue}
    Function     fg={blue}
    Type         fg={yellow}
    Statement    fg={green} bold
    Keyword      fg={green}
    Special      fg={red}
    SpecialCharacter bg={base02}

    Error        us=wave uc={red}
    SpellError   us=wave uc={orange}
    Tooltip      fg=black bg=ffffed

    DiffDelete   bg={base02} fg={red}
    DiffInsert   bg={base02} fg={green}
    DiffReplace  bg={base02} fg={blue}
    DiffReplaceReplace bg={base03}
    '''
# }}}

THEMES = {
    'wombat-dark':  # {{{
    '''
    CursorLine   bg={cursor_loc}
    CursorColumn bg={cursor_loc}
    ColorColumn  bg={cursor_loc}
    HighlightRegion bg=3d3d3d
    MatchParen   bg=444444
    Pmenu        fg=f6f3e8 bg=444444
    PmenuSel     fg=yellow bg={identifier}
    Tooltip      fg=black bg=ffffed

    Cursor       bg=656565
    Normal       fg=f6f3e8 bg=242424
    LineNr       fg=857b6f bg=000000
    LineNrC      fg=yellow
    Visual       fg=black bg=888888

    Comment      fg={comment}
    Todo         fg=8f8f8f
    String       fg={string}
    Constant     fg={constant}
    Number       fg={constant}
    PreProc      fg={constant}
    Identifier   fg={identifier}
    Function     fg={identifier}
    Type         fg={identifier}
    Statement    fg={keyword}
    Keyword      fg={keyword}
    Special      fg=e7f6da
    Error        us=wave uc=red
    SpellError   us=wave uc=orange
    SpecialCharacter bg={cursor_loc}

    DiffDelete   bg=341414 fg=642424
    DiffInsert   bg=143414 fg=246424
    DiffReplace  bg=141434 fg=242464
    DiffReplaceReplace bg=002050

    '''.format(
        cursor_loc='323232',
        identifier='cae682',
        comment='99968b',
        string='95e454',
        keyword='8ac6f2',
        constant='e5786d'),  # }}}

    'pyte-light':  # {{{
    '''
    CursorLine   bg={cursor_loc}
    CursorColumn bg={cursor_loc}
    ColorColumn  bg={cursor_loc}
    HighlightRegion bg=E3F988
    MatchParen   bg=cfcfcf
    Pmenu        fg=white bg=808080
    PmenuSel     fg=white bg=808080
    Tooltip      fg=black bg=ffffed

    Cursor       fg=black bg=b0b4b8
    Normal       fg=404850 bg=f0f0f0
    LineNr       fg=white bg=8090a0
    LineNrC      fg=yellow
    Visual       fg=white bg=8090a0

    Comment      fg={comment} italic
    Todo         fg={comment} italic bold
    String       fg={string}
    Constant     fg={constant}
    Number       fg={constant}
    PreProc      fg={constant}
    Identifier   fg={identifier}
    Function     fg={identifier}
    Type         fg={identifier}
    Statement    fg={keyword}
    Keyword      fg={keyword}
    Special      fg=70a0d0 italic
    SpecialCharacter bg={cursor_loc}
    Error        us=wave uc=red
    SpellError   us=wave uc=orange

    DiffDelete   bg=rgb(255,180,200) fg=rgb(200,80,110)
    DiffInsert   bg=rgb(180,255,180) fg=rgb(80,210,80)
    DiffReplace  bg=rgb(206,226,250) fg=rgb(90,130,180)
    DiffReplaceReplace bg=rgb(180,210,250)

    '''.format(
        cursor_loc='F8DE7E',
        identifier='7b5694',
        comment='a0b0c0',
        string='4070a0',
        keyword='007020',
        constant='a07040'),  # }}}

    'solarized-x-dark': SOLARIZED.format(**SLDX),
    'solarized-dark': SOLARIZED.format(**SLD),
    'solarized-light': SOLARIZED.format(**SLL),
    'solarized-x-light': SOLARIZED.format(**SLLX),

}

def read_color(col):
    if QColor.isValidColor(col):
        return QBrush(QColor(col))
    if col.startswith('rgb('):
        r, g, b = map(int, (x.strip() for x in col[4:-1].split(',')))
        return QBrush(QColor(r, g, b))
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
underline_styles = {x:getattr(SyntaxTextCharFormat, u(x)) for x in underline_styles}

def highlight_to_char_format(h):
    ans = SyntaxTextCharFormat()
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
        return getattr(THEMES[default_theme()][name], attr).color()

def theme_format(theme, name):
    try:
        h = theme[name]
    except KeyError:
        h = THEMES[default_theme()][name]
    return highlight_to_char_format(h)
