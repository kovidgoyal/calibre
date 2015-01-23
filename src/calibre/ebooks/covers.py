#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re, random, unicodedata
from collections import namedtuple
from contextlib import contextmanager
from math import ceil, sqrt, cos, sin, atan2
from future_builtins import map, zip
from itertools import chain

from PyQt5.Qt import (
    QImage, Qt, QFont, QPainter, QPointF, QTextLayout, QTextOption,
    QFontMetrics, QTextCharFormat, QColor, QRect, QBrush, QLinearGradient,
    QPainterPath, QPen, QRectF
)

from calibre import force_unicode, fit_image
from calibre.constants import __appname__, __version__
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import ensure_app, config, load_builtin_fonts, pixmap_to_data
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.config import JSONConfig

# Default settings {{{
cprefs = JSONConfig('cover_generation')
cprefs.defaults['title_font_size'] = 120  # px
cprefs.defaults['subtitle_font_size'] = 80  # px
cprefs.defaults['footer_font_size'] = 80  # px
cprefs.defaults['cover_width'] = 1200  # px
cprefs.defaults['cover_height'] = 1600  # px
cprefs.defaults['title_font_family'] = None
cprefs.defaults['subtitle_font_family'] = None
cprefs.defaults['footer_font_family'] = None
cprefs.defaults['color_themes'] = {}
cprefs.defaults['disabled_color_themes'] = []
cprefs.defaults['disabled_styles'] = []
cprefs.defaults['title_template'] = '<b>{title}'
cprefs.defaults['subtitle_template'] = '''{series:'test($, strcat("<i>", $, "</i> - ", raw_field("formatted_series_index")), "")'}'''
cprefs.defaults['footer_template'] = r'''program:
# Show at most two authors, on separate lines.
authors = field('authors');
num = count(authors, ' &amp; ');
authors = sublist(authors, 0, 2, ' &amp; ');
authors = list_re(authors, ' &amp; ', '(.+)', '<b>\1');
authors = re(authors, ' &amp; ', '<br>');
re(authors, '&amp;&amp;', '&amp;')
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
            text, formats = parse_text_formatting(sanitize(text))
            l = QTextLayout(unescape_formatting(text), font, img)
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
    title, subtitle, footer = title, subtitle, footer
    title_font = QFont(prefs.title_font_family or 'Liberation Serif')
    title_font.setPixelSize(prefs.title_font_size)
    title_block = Block(title, width, title_font, img, max_height, style.TITLE_ALIGN)
    title_block.position = style.hmargin, style.vmargin
    subtitle_block = Block()
    if subtitle:
        subtitle_font = QFont(prefs.subtitle_font_family or 'Liberation Sans')
        subtitle_font.setPixelSize(prefs.subtitle_font_size)
        gap = 2 * title_block.leading
        mh = max_height - title_block.height - gap
        subtitle_block = Block(subtitle, width, subtitle_font, img, mh, style.SUBTITLE_ALIGN)
        subtitle_block.position = style.hmargin, title_block.position.y + title_block.height + gap

    footer_font = QFont(prefs.footer_font_family or 'Liberation Serif')
    footer_font.setPixelSize(prefs.footer_font_size)
    footer_block = Block(footer, width, footer_font, img, max_height, style.FOOTER_ALIGN)
    footer_block.position = style.hmargin, img.height() - style.vmargin - footer_block.height

    return title_block, subtitle_block, footer_block

# }}}

# Format text using templates {{{
def sanitize(s):
    return unicodedata.normalize('NFC', clean_xml_chars(clean_ascii_chars(force_unicode(s or ''))))

_formatter = None
_template_cache = {}

def escape_formatting(val):
    return val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def unescape_formatting(val):
    return val.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')

class Formatter(SafeFormat):

    def get_value(self, orig_key, args, kwargs):
        ans = SafeFormat.get_value(self, orig_key, args, kwargs)
        return escape_formatting(ans)

def formatter():
    global _formatter
    if _formatter is None:
        _formatter = Formatter()
    return _formatter

def format_fields(mi, prefs):
    f = formatter()
    def safe_format(field):
        return f.safe_format(
            getattr(prefs, field), mi, _('Template error'), mi, template_cache=_template_cache
        )
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

# Colors {{{
ColorTheme = namedtuple('ColorTheme', 'color1 color2 contrast_color1 contrast_color2')

def to_theme(x):
    return {k:v for k, v in zip(ColorTheme._fields[:4], x.split())}

fallback_colors = to_theme('ffffff 000000 000000 ffffff')

default_color_themes = {
    'Earth' : to_theme('e8d9ac c7b07b 564628 382d1a'),
    'Grass' : to_theme('d8edb5 abc8a4 375d3b 183128'),
    'Water' : to_theme('d3dcf2 829fe4 00448d 00305a'),
    'Silver': to_theme('e6f1f5 aab3b6 6e7476 3b3e40'),
}


def theme_to_colors(theme):
    colors = {k:QColor('#' + theme[k]) for k in ColorTheme._fields}
    return ColorTheme(**colors)

def load_color_themes(prefs):
    t = default_color_themes.copy()
    t.update(prefs.color_themes)
    disabled = frozenset(prefs.disabled_color_themes)
    ans = [theme_to_colors(v) for k, v in t.iteritems() if k not in disabled]
    if not ans:
        # Ignore disabled and return only the builtin color themes
        ans = [theme_to_colors(v) for k, v in default_color_themes.iteritems()]
    return ans

def color(color_theme, name):
    ans = getattr(color_theme, name)
    if not ans.isValid():
        ans = QColor('#' + fallback_colors[name])
    return ans

# }}}

# Styles {{{
class Style(object):

    TITLE_ALIGN = SUBTITLE_ALIGN = FOOTER_ALIGN = Qt.AlignHCenter | Qt.AlignTop

    def __init__(self, color_theme, prefs):
        self.load_colors(color_theme)
        self.calculate_margins(prefs)

    def calculate_margins(self, prefs):
        self.hmargin = int((50 / 600) * prefs.cover_width)
        self.vmargin = int((50 / 800) * prefs.cover_height)

    def load_colors(self, color_theme):
        self.color1 = color(color_theme, 'color1')
        self.color2 = color(color_theme, 'color2')
        self.ccolor1 = color(color_theme, 'contrast_color1')
        self.ccolor2 = color(color_theme, 'contrast_color2')

class Cross(Style):

    NAME = 'The Cross'
    GUI_NAME = _('The Cross')

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        painter.fillRect(rect, self.color1)
        r = QRect(0, int(title_block.position.y), rect.width(),
                  title_block.height + subtitle_block.height + subtitle_block.line_spacing // 2 + title_block.leading)
        painter.save()
        p = QPainterPath()
        p.addRoundedRect(QRectF(r), 10, 10 * r.width()/r.height(), Qt.RelativeSize)
        painter.setClipPath(p)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(r, self.color2)
        painter.restore()
        r = QRect(0, 0, int(title_block.position.x), rect.height())
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

def rotate_vector(angle, x, y):
    return x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)

def draw_curved_line(painter_path, dx, dy, c1_frac, c1_amp, c2_frac, c2_amp):
    length = sqrt(dx * dx + dy * dy)
    angle = atan2(dy, dx)
    c1 = QPointF(*rotate_vector(angle, c1_frac * length, c1_amp * length))
    c2 = QPointF(*rotate_vector(angle, c2_frac * length, c2_amp * length))
    pos = painter_path.currentPosition()
    painter_path.cubicTo(pos + c1, pos + c2, pos + QPointF(dx, dy))

class Banner(Style):

    NAME = 'Banner'
    GUI_NAME = _('Banner')
    GRADE = 0.07

    def calculate_margins(self, prefs):
        Style.calculate_margins(self, prefs)
        self.hmargin = int(0.15 * prefs.cover_width)
        self.fold_width = int(0.1 * prefs.cover_width)

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        painter.fillRect(rect, self.color1)
        top = title_block.position.y + 10
        extra_spacing = subtitle_block.line_spacing // 2 if subtitle_block.line_spacing else title_block.line_spacing // 3
        height = title_block.height + subtitle_block.height + extra_spacing + title_block.leading
        right = rect.right() - self.hmargin
        width = right - self.hmargin

        # Draw main banner
        p = main = QPainterPath(QPointF(self.hmargin, top))
        draw_curved_line(p, rect.width() - 2 * self.hmargin, 0, 0.1, -0.1, 0.9, -0.1)
        deltax = self.GRADE * height
        p.lineTo(right + deltax, top + height)
        right_corner = p.currentPosition()
        draw_curved_line(p, - width - 2 * deltax, 0, 0.1, 0.05, 0.9, 0.05)
        left_corner = p.currentPosition()
        p.closeSubpath()

        # Draw fold rectangles
        rwidth = self.fold_width
        yfrac = 0.1
        width23 = int(0.67 * rwidth)
        rtop = top + height * yfrac

        def draw_fold(x, m=1, corner=left_corner):
            ans = p = QPainterPath(QPointF(x, rtop))
            draw_curved_line(p, rwidth*m, 0, 0.1, 0.1*m, 0.5, -0.2*m)
            fold_upper = p.currentPosition()
            p.lineTo(p.currentPosition() + QPointF(-deltax*m, height))
            fold_corner = p.currentPosition()
            draw_curved_line(p, -rwidth*m, 0, 0.2, -0.1*m, 0.8, -0.1*m)
            draw_curved_line(p, deltax*m, -height, 0.2, 0.1*m, 0.8, 0.1*m)
            p = inner_fold = QPainterPath(corner)
            dp = fold_corner - p.currentPosition()
            draw_curved_line(p, dp.x(), dp.y(), 0.5, 0.3*m, 1, 0*m)
            p.lineTo(fold_upper), p.closeSubpath()
            return ans, inner_fold

        left_fold, left_inner = draw_fold(self.hmargin - width23)
        right_fold, right_inner = draw_fold(right + width23, m=-1, corner=right_corner)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.ccolor2)
        pen.setWidth(3)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        for r in (left_fold, right_fold):
            painter.fillPath(r, QBrush(self.color2))
            painter.drawPath(r)
        for r in (left_inner, right_inner):
            painter.fillPath(r, QBrush(self.color2.darker()))
            painter.drawPath(r)
        painter.fillPath(main, QBrush(self.color2))
        painter.drawPath(main)
        painter.restore()
        return self.ccolor2, self.ccolor2, self.ccolor1

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

def load_styles(prefs, respect_disabled=True):
    disabled = frozenset(prefs.disabled_styles) if respect_disabled else ()
    ans = tuple(x for x in globals().itervalues() if
            isinstance(x, type) and issubclass(x, Style) and x is not Style and x.NAME not in disabled)
    if not ans and disabled:
        # If all styles have been disabled, ignore the disabling and return all
        # the styles
        ans = load_styles(prefs, respect_disabled=False)
    return ans

# }}}

def init_environment():
    ensure_app()
    load_builtin_fonts()

def generate_cover(mi, prefs=None, as_qimage=False):
    init_environment()
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
    img.setText('Generated cover', '%s %s' % (__appname__, __version__))
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

def create_cover(title, authors, series=None, series_index=1, prefs=None, as_qimage=False):
    ' Create a cover from the specified title, author and series. Any user set'
    ' templates are ignored, to ensure that the specified metadata is used. '
    mi = Metadata(title, authors)
    if series:
        mi.series, mi.series_index = series, series_index
    d = cprefs.defaults
    prefs = override_prefs(
        prefs or cprefs, title_template=d['title_template'], subtitle_template=d['subtitle_template'], footer_template=d['footer_template'])
    return generate_cover(mi, prefs=prefs, as_qimage=as_qimage)

def calibre_cover2(title, author_string='', series_string='', prefs=None, as_qimage=False):
    init_environment()
    title, subtitle, footer = '<b>' + escape_formatting(title), '<i>' + escape_formatting(series_string), '<b>' + escape_formatting(author_string)
    prefs = prefs or cprefs
    prefs = {k:prefs.get(k) for k in cprefs.defaults}
    scale = 800. / prefs['cover_height']
    scale_cover(prefs, scale)
    prefs = Prefs(**prefs)
    img = QImage(prefs.cover_width, prefs.cover_height, QImage.Format_ARGB32)
    img.fill(Qt.white)
    # colors = to_theme('ffffff ffffff 000000 000000')
    color_theme = theme_to_colors(fallback_colors)
    class CalibeLogoStyle(Style):
        NAME = GUI_NAME = 'calibre'
        def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
            top = title_block.position.y + 10
            extra_spacing = subtitle_block.line_spacing // 2 if subtitle_block.line_spacing else title_block.line_spacing // 3
            height = title_block.height + subtitle_block.height + extra_spacing + title_block.leading
            top += height + 25
            bottom = footer_block.position.y - 50
            logo = QImage(I('library.png'))
            pwidth, pheight = rect.width(), bottom - top
            scaled, width, height = fit_image(logo.width(), logo.height(), pwidth, pheight)
            x, y = (pwidth - width) // 2, (pheight - height) // 2
            rect = QRect(x, top + y, width, height)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(rect, logo)
            return self.ccolor1, self.ccolor1, self.ccolor1
    style = CalibeLogoStyle(color_theme, prefs)
    title_block, subtitle_block, footer_block = layout_text(
        prefs, img, title, subtitle, footer, img.height() // 3, style)
    p = QPainter(img)
    rect = QRect(0, 0, img.width(), img.height())
    colors = style(p, rect, color_theme, title_block, subtitle_block, footer_block)
    for block, color in zip((title_block, subtitle_block, footer_block), colors):
        p.setPen(color)
        block.draw(p)
    p.end()
    img.setText('Generated cover', '%s %s' % (__appname__, __version__))
    if as_qimage:
        return img
    return pixmap_to_data(img)

def scale_cover(prefs, scale):
    for x in ('cover_width', 'cover_height', 'title_font_size', 'subtitle_font_size', 'footer_font_size'):
        prefs[x] = int(scale * prefs[x])

def generate_masthead(title, output_path=None, width=600, height=60, as_qimage=False, font_family=None):
    init_environment()
    font_family = font_family or cprefs['title_font_family'] or 'Liberation Serif'
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(Qt.white)
    p = QPainter(img)
    f = QFont(font_family)
    f.setPixelSize((height * 3) // 4), f.setBold(True)
    p.setFont(f)
    p.drawText(img.rect(), Qt.AlignLeft | Qt.AlignVCenter, sanitize(title))
    p.end()
    if as_qimage:
        return img
    data = pixmap_to_data(img)
    if output_path is None:
        return data
    with open(output_path, 'wb') as f:
        f.write(data)

def test(scale=0.25):
    from PyQt5.Qt import QLabel, QApplication, QPixmap, QMainWindow, QWidget, QScrollArea, QGridLayout
    app = QApplication([])
    mi = Metadata('xxx', ['Kovid Goyal', 'John & Doe', 'Author'])
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
            scale_cover(prefs, scale)
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
