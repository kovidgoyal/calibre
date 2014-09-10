#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, random
from collections import namedtuple
from contextlib import contextmanager
from math import ceil
from future_builtins import map, zip
from itertools import chain, repeat

from PyQt5.Qt import (
    QImage, Qt, QFont, QPainter, QPointF, QTextLayout, QTextOption,
    QFontMetrics, QTextCharFormat, QColor, QRect, QBrush, QLinearGradient
)

from calibre import force_unicode
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import ensure_app, config, load_builtin_fonts, pixmap_to_data
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.config import JSONConfig

# Default settings {{{
cprefs = JSONConfig('cover_generation')
cprefs.defaults['title_font_size'] = 60  # px
cprefs.defaults['subtitle_font_size'] = 40  # px
cprefs.defaults['footer_font_size'] = 40  # px
cprefs.defaults['cover_width'] = 600  # px
cprefs.defaults['cover_height'] = 800  # px
cprefs.defaults['title_font_family'] = 'Liberation Serif'
cprefs.defaults['subtitle_font_family'] = 'Liberation Sans'
cprefs.defaults['footer_font_family'] = 'Liberation Serif'
cprefs.defaults['color_themes'] = {}
cprefs.defaults['disabled_color_themes'] = []
cprefs.defaults['disabled_styles'] = []
cprefs.defaults['title_template'] = '<b>{title}'
cprefs.defaults['subtitle_template'] = '''{series:'test($, strcat("<i>", $, "</i> - ", raw_field("formatted_series_index")), "")'}'''
cprefs.defaults['footer_template'] = r'''program:
# Show at most two authors, on separate lines.
authors = field('authors');
num = count(authors, ' & ');
authors = cmp(num, 2, authors, authors, sublist(authors, 0, 2, ' & '));
authors = list_re(authors, ' & ', '(.+)', '<b>\1');
authors = re(authors, ' & ', '<br>');
re(authors, '&&', '&')
'''
Prefs = namedtuple('Prefs', ' '.join(sorted(cprefs.defaults)))
# }}}

# Draw text {{{

Point = namedtuple('Point', 'x y')

def parse_text_formatting(text):
    pos = 0
    tokens = []
    for m in re.finditer(r'</?([a-zA-Z1-6]+)/?>', text):
        q = text[pos:m.start()]
        if q:
            tokens.append((False, q))
        tokens.append((True, (m.group(1).lower(), '/' in m.group()[:2])))
        pos = m.end()
    if tokens:
        if text[pos:]:
            tokens.append((False, text[pos:]))
    else:
        tokens = [(False, text)]

    ranges, open_ranges, text = [], [], []
    offset = 0
    for is_tag, tok in tokens:
        if is_tag:
            tag, closing = tok
            if closing:
                if open_ranges:
                    r = open_ranges.pop()
                    r[-1] = offset - r[-2]
                    if r[-1] > 0:
                        ranges.append(r)
            else:
                if tag in {'b', 'strong', 'i', 'em'}:
                    open_ranges.append([tag, offset, -1])
        else:
            offset += len(tok)
            text.append(tok)
    text = ''.join(text)
    formats = []
    for tag, start, length in chain(ranges, open_ranges):
        fmt = QTextCharFormat()
        if tag in {'b', 'strong'}:
            fmt.setFontWeight(QFont.Bold)
        elif tag in {'i', 'em'}:
            fmt.setFontItalic(True)
        else:
            continue
        if length == -1:
            length = len(text) - start
        if length > 0:
            r = QTextLayout.FormatRange()
            r.format = fmt
            r.start, r.length = start, length
            formats.append(r)
    return text, formats

class Block(object):

    def __init__(self, text='', width=0, font=None, img=None, max_height=100, align=Qt.AlignCenter):
        self.layouts = []
        self._position = Point(0, 0)
        self.leading = self.line_spacing = 0
        if font is not None:
            fm = QFontMetrics(font, img)
            self.leading = fm.leading()
            self.line_spacing = fm.lineSpacing()
        for text in text.split('<br>') if text else ():
            text, formats = parse_text_formatting(text)
            l = QTextLayout(text, font, img)
            l.setAdditionalFormats(formats)
            to = QTextOption(align)
            to.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            l.setTextOption(to)

            l.beginLayout()
            height = 0
            while height + 3*self.leading < max_height:
                line = l.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                height += self.leading
                line.setPosition(QPointF(0, height))
                height += line.height()
            max_height -= height
            l.endLayout()
            if self.layouts:
                self.layouts.append(self.leading)
            else:
                self._position = Point(l.position().x(), l.position().y())
            self.layouts.append(l)
        if self.layouts:
            self.layouts.append(self.leading)

    @property
    def height(self):
        return int(ceil(sum(l if isinstance(l, (int, float)) else l.boundingRect().height() for l in self.layouts)))

    @dynamic_property
    def position(self):
        def fget(self):
            return self._position
        def fset(self, (x, y)):
            self._position = Point(x, y)
            if self.layouts:
                self.layouts[0].setPosition(QPointF(x, y))
                y += self.layouts[0].boundingRect().height()
                for l in self.layouts[1:]:
                    if isinstance(l, (int, float)):
                        y += l
                    else:
                        l.setPosition(QPointF(x, y))
                        y += l.boundingRect().height()
        return property(fget=fget, fset=fset)

    def draw(self, painter):
        for l in self.layouts:
            if hasattr(l, 'draw'):
                # Etch effect for the text
                painter.save()
                painter.setPen(QColor(255, 255, 255, 125))
                l.draw(painter, QPointF(1, 1))
                painter.restore()
                l.draw(painter, QPointF())

def layout_text(prefs, img, title, subtitle, footer, max_height, style):
    width = img.width() - 2 * style.hmargin
    title_font = QFont(prefs.title_font_family)
    title_font.setPixelSize(prefs.title_font_size)
    title_block = Block(title, width, title_font, img, max_height, style.TITLE_ALIGN)
    title_block.position = style.hmargin, style.vmargin
    subtitle_block = Block()
    if subtitle:
        subtitle_font = QFont(prefs.subtitle_font_family)
        subtitle_font.setPixelSize(prefs.subtitle_font_size)
        gap = 2 * title_block.leading
        mh = max_height - title_block.height - gap
        subtitle_block = Block(subtitle, width, subtitle_font, img, mh, style.SUBTITLE_ALIGN)
        subtitle_block.position = style.hmargin, title_block.position[0] + title_block.height + gap

    footer_font = QFont(prefs.footer_font_family)
    footer_font.setPixelSize(prefs.footer_font_size)
    footer_block = Block(footer, width, footer_font, img, max_height, style.FOOTER_ALIGN)
    footer_block.position = style.hmargin, img.height() - style.vmargin - footer_block.height

    return title_block, subtitle_block, footer_block

# }}}

# Format text using templates {{{
def sanitize(s):
    return clean_xml_chars(clean_ascii_chars(force_unicode(s or '')))

_formatter = None
_template_cache = {}

def formatter():
    global _formatter
    if _formatter is None:
        _formatter = SafeFormat()
    return _formatter

def format_fields(mi, prefs):
    f = formatter()
    def safe_format(field):
        return sanitize(f.safe_format(
            getattr(prefs, field), mi, _('Template error'), mi, template_cache=_template_cache
        ))
    return map(safe_format, ('title_template', 'subtitle_template', 'footer_template'))

@contextmanager
def preserve_fields(obj, fields):
    if isinstance(fields, basestring):
        fields = fields.split()
    null = object()
    mem = {f:getattr(obj, f, null) for f in fields}
    try:
        yield
    finally:
        for f, val in mem.iteritems():
            if val is null:
                delattr(obj, f)
            else:
                setattr(obj, f, val)

def format_text(mi, prefs):
    with preserve_fields(mi, 'authors formatted_series_index'):
        mi.authors = [a for a in mi.authors if a != _('Unknown')]
        mi.formatted_series_index = fmt_sidx(mi.series_index or 0, use_roman=config['use_roman_numerals_for_series_number'])
        return tuple(format_fields(mi, prefs))
# }}}

default_color_themes = {
    'Mocha': 'e8d9ac c7b07b 564628 382d1a',
}

ColorTheme = namedtuple('ColorTheme', 'color1 color2 contrast_color1 contrast_color2')

def theme_to_colors(theme):
    colors = [QColor('#' + c) for c in theme.split()]
    colors += list(repeat(QColor(), len(ColorTheme._fields) - len(colors)))
    return ColorTheme(*colors)

def load_color_themes(prefs):
    t = default_color_themes.copy()
    t.update(prefs.color_themes)
    disabled = frozenset(prefs.disabled_color_themes)
    return [theme_to_colors(v) for k, v in t.iteritems() if k not in disabled]

def color(color_theme, name, fallback=Qt.white):
    ans = getattr(color_theme, name)
    if not ans.isValid():
        ans = QColor(fallback)
    return ans

def load_colors(color_theme):
    c1 = color(color_theme, 'color1', Qt.white)
    c2 = color(color_theme, 'color2', Qt.black)
    cc1 = color(color_theme, 'contrast_color1', Qt.white)
    cc2 = color(color_theme, 'contrast_color2', Qt.black)
    return c1, c2, cc1, cc2

class Style(object):

    TITLE_ALIGN = SUBTITLE_ALIGN = FOOTER_ALIGN = Qt.AlignHCenter | Qt.AlignTop

    def __init__(self, color_theme, prefs):
        self.load_colors(color_theme)
        self.calculate_margins(prefs)

    def calculate_margins(self, prefs):
        self.hmargin = (50 / 600) * prefs.cover_width
        self.vmargin = (50 / 800) * prefs.cover_height

    def load_colors(self, color_theme):
        self.color1 = color(color_theme, 'color1', Qt.white)
        self.color2 = color(color_theme, 'color2', Qt.black)
        self.ccolor1 = color(color_theme, 'contrast_color1', Qt.white)
        self.ccolor2 = color(color_theme, 'contrast_color2', Qt.black)

class Cross(Style):

    NAME = 'The Cross'
    GUI_NAME = _('The Cross')

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        painter.fillRect(rect, self.color1)
        r = QRect(0, 0, int(title_block.position.x), rect.height())
        painter.fillRect(r, self.color2)
        r = QRect(0, int(title_block.position.y), rect.width(), title_block.height + subtitle_block.height + title_block.line_spacing // 3)
        painter.fillRect(r, self.color2)
        return self.ccolor2, self.ccolor2, self.ccolor1

class Half(Style):

    NAME = 'Half and Half'
    GUI_NAME = _('Half and Half')

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        g = QLinearGradient(QPointF(0, 0), QPointF(0, rect.height()))
        g.setStops([(0, self.color1), (0.7, self.color2), (1, self.color1)])
        painter.fillRect(rect, QBrush(g))
        return self.ccolor1, self.ccolor1, self.ccolor1

class Blocks(Style):

    NAME = 'Blocks'
    GUI_NAME = _('Blocks')
    FOOTER_ALIGN = Qt.AlignRight | Qt.AlignTop

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        painter.fillRect(rect, self.color1)
        y = rect.height() - rect.height() // 3
        r = QRect(rect)
        r.setBottom(y)
        painter.fillRect(rect, self.color1)
        r = QRect(rect)
        r.setTop(y)
        painter.fillRect(r, self.color2)
        return self.ccolor1, self.ccolor1, self.ccolor2

def all_styles():
    return set(
        x.NAME for x in globals().itervalues() if
        isinstance(x, type) and issubclass(x, Style) and x is not Style
    )

def load_styles(prefs):
    disabled = frozenset(prefs.disabled_styles)
    return tuple(x for x in globals().itervalues() if
            isinstance(x, type) and issubclass(x, Style) and x is not Style and x.NAME not in disabled)

def generate_cover(mi, prefs=None, as_qimage=False):
    ensure_app()
    load_builtin_fonts()
    prefs = prefs or cprefs
    prefs = {k:prefs.get(k) for k in cprefs.defaults}
    prefs = Prefs(**prefs)
    color_theme = random.choice(load_color_themes(prefs))
    style = random.choice(load_styles(prefs))(color_theme, prefs)
    title, subtitle, footer = format_text(mi, prefs)
    img = QImage(prefs.cover_width, prefs.cover_height, QImage.Format_ARGB32)
    title_block, subtitle_block, footer_block = layout_text(
        prefs, img, title, subtitle, footer, img.height() // 3, style)
    p = QPainter(img)
    rect = QRect(0, 0, img.width(), img.height())
    colors = style(p, rect, color_theme, title_block, subtitle_block, footer_block)
    for block, color in zip((title_block, subtitle_block, footer_block), colors):
        p.setPen(color)
        block.draw(p)
    p.end()
    if as_qimage:
        return img
    return pixmap_to_data(img)

def override_prefs(base_prefs, **overrides):
    ans = {k:overrides.get(k, base_prefs[k]) for k in cprefs.defaults}
    override_color_theme = overrides.get('override_color_theme')
    if override_color_theme is not None:
        all_themes = set(default_color_themes) | set(ans['color_themes'])
        if override_color_theme in all_themes:
            all_themes.discard(override_color_theme)
            ans['disabled_color_themes'] = all_themes
    override_style = overrides.get('override_style')
    if override_style is not None:
        styles = all_styles()
        if override_style in styles:
            styles.discard(override_style)
            ans['disabled_styles'] = styles

    return ans

def test(scale=2):
    from PyQt5.Qt import QLabel, QApplication, QPixmap, QMainWindow, QWidget, QScrollArea, QGridLayout
    from calibre.ebooks.metadata.book.base import Metadata
    app = QApplication([])
    mi = Metadata('xxx', ['Kovid Goyal', 'John Q. Doe', 'Author'])
    mi.series = 'A series of styles'
    m = QMainWindow()
    sa = QScrollArea(m)
    w = QWidget(m)
    sa.setWidget(w)
    l = QGridLayout(w)
    w.setLayout(l), l.setSpacing(30)
    labels = []
    for r, color in enumerate(sorted(default_color_themes)):
        for c, style in enumerate(sorted(all_styles())):
            mi.series_index = c + 1
            mi.title = 'An algorithmic cover [%s]' % color
            prefs = override_prefs(cprefs, override_color_theme=color, override_style=style)
            for x in ('cover_width', 'cover_height', 'title_font_size', 'subtitle_font_size', 'footer_font_size'):
                prefs[x] //= scale
            img = generate_cover(mi, prefs=prefs, as_qimage=True)
            la = QLabel()
            la.setPixmap(QPixmap.fromImage(img))
            l.addWidget(la, r, c)
            labels.append(la)
    m.setCentralWidget(sa)
    w.resize(w.sizeHint())
    m.show()
    app.exec_()

if __name__ == '__main__':
    test()
