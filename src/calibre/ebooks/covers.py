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
    QPainterPath, QPen, QRectF, QTransform, QRadialGradient
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

_use_roman = None


def get_use_roman():
    global _use_roman
    if _use_roman is None:
        return config['use_roman_numerals_for_series_number']
    return _use_roman


def set_use_roman(val):
    global _use_roman
    _use_roman = bool(val)

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
            offset += len(tok.replace('&amp;', '&'))
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
                painter.setRenderHints(QPainter.TextAntialiasing | QPainter.Antialiasing)
                painter.save()
                painter.setPen(QColor(255, 255, 255, 125))
                l.draw(painter, QPointF(1, 1))
                painter.restore()
                l.draw(painter, QPointF())
                painter.restore()


def layout_text(prefs, img, title, subtitle, footer, max_height, style):
    width = img.width() - 2 * style.hmargin
    title, subtitle, footer = title, subtitle, footer
    title_font = QFont(prefs.title_font_family or 'Liberation Serif')
    title_font.setPixelSize(prefs.title_font_size)
    title_font.setStyleStrategy(QFont.PreferAntialias)
    title_block = Block(title, width, title_font, img, max_height, style.TITLE_ALIGN)
    title_block.position = style.hmargin, style.vmargin
    subtitle_block = Block()
    if subtitle:
        subtitle_font = QFont(prefs.subtitle_font_family or 'Liberation Sans')
        subtitle_font.setPixelSize(prefs.subtitle_font_size)
        subtitle_font.setStyleStrategy(QFont.PreferAntialias)
        gap = 2 * title_block.leading
        mh = max_height - title_block.height - gap
        subtitle_block = Block(subtitle, width, subtitle_font, img, mh, style.SUBTITLE_ALIGN)
        subtitle_block.position = style.hmargin, title_block.position.y + title_block.height + gap

    footer_font = QFont(prefs.footer_font_family or 'Liberation Serif')
    footer_font.setStyleStrategy(QFont.PreferAntialias)
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
        mi.formatted_series_index = fmt_sidx(mi.series_index or 0, use_roman=get_use_roman())
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
    GUI_NAME = _('Half and half')

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
        top = title_block.position.y + 2
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


class Ornamental(Style):

    NAME = 'Ornamental'
    GUI_NAME = _('Ornamental')

    # SVG vectors {{{
    CORNER_VECTOR = "m 67.791903,64.260958 c -4.308097,-2.07925 -4.086719,-8.29575 0.334943,-9.40552 4.119758,-1.03399 8.732363,5.05239 5.393055,7.1162 -0.55,0.33992 -1,1.04147 -1,1.55902 0,1.59332 2.597425,1.04548 5.365141,-1.1316 1.999416,-1.57274 2.634859,-2.96609 2.634859,-5.7775 0,-9.55787 -9.827495,-13.42961 -24.43221,-9.62556 -3.218823,0.83839 -5.905663,1.40089 -5.970755,1.25 -0.06509,-0.1509 -0.887601,-1.19493 -1.827799,-2.32007 -1.672708,-2.00174 -1.636693,-2.03722 1.675668,-1.65052 1.861815,0.21736 6.685863,-0.35719 10.720107,-1.27678 12.280767,-2.79934 20.195487,-0.0248 22.846932,8.0092 3.187273,9.65753 -6.423297,17.7497 -15.739941,13.25313 z m 49.881417,-20.53932 c -3.19204,-2.701 -3.72967,-6.67376 -1.24009,-9.16334 2.48236,-2.48236 5.35141,-2.67905 7.51523,-0.51523 1.85966,1.85966 2.07045,6.52954 0.37143,8.22857 -2.04025,2.04024 3.28436,1.44595 6.92316,-0.77272 9.66959,-5.89579 0.88581,-18.22422 -13.0777,-18.35516 -5.28594,-0.0496 -10.31098,1.88721 -14.26764,5.4991 -1.98835,1.81509 -2.16454,1.82692 -2.7936,0.18763 -0.40973,-1.06774 0.12141,-2.82197 1.3628,-4.50104 2.46349,-3.33205 1.67564,-4.01299 -2.891784,-2.49938 -2.85998,0.94777 -3.81038,2.05378 -5.59837,6.51495 -1.184469,2.95536 -3.346819,6.86882 -4.805219,8.69657 -1.4584,1.82776 -2.65164,4.02223 -2.65164,4.87662 0,3.24694 -4.442667,0.59094 -5.872557,-3.51085 -1.361274,-3.90495 0.408198,-8.63869 4.404043,-11.78183 5.155844,-4.05558 1.612374,-3.42079 -9.235926,1.65457 -12.882907,6.02725 -16.864953,7.18038 -24.795556,7.18038 -8.471637,0 -13.38802,-1.64157 -17.634617,-5.88816 -2.832233,-2.83224 -3.849773,-4.81378 -4.418121,-8.6038 -1.946289,-12.9787795 8.03227,-20.91713135 19.767685,-15.7259993 5.547225,2.4538018 6.993631,6.1265383 3.999564,10.1557393 -5.468513,7.35914 -15.917883,-0.19431 -10.657807,-7.7041155 1.486298,-2.1219878 1.441784,-2.2225068 -0.984223,-2.2225068 -1.397511,0 -4.010527,1.3130878 -5.806704,2.9179718 -2.773359,2.4779995 -3.265777,3.5977995 -3.265777,7.4266705 0,5.10943 2.254112,8.84197 7.492986,12.40748 8.921325,6.07175 19.286666,5.61396 37.12088,-1.63946 15.35037,-6.24321 21.294999,-7.42408 34.886123,-6.92999 11.77046,0.4279 19.35803,3.05537 24.34054,8.42878 4.97758,5.3681 2.53939,13.58271 -4.86733,16.39873 -4.17361,1.58681 -11.00702,1.19681 -13.31978,-0.76018 z m 26.50156,-0.0787 c -2.26347,-2.50111 -2.07852,-7.36311 0.39995,-10.51398 2.68134,-3.40877 10.49035,-5.69409 18.87656,-5.52426 l 6.5685,0.13301 -7.84029,0.82767 c -8.47925,0.89511 -12.76997,2.82233 -16.03465,7.20213 -1.92294,2.57976 -1.96722,3.00481 -0.57298,5.5 1.00296,1.79495 2.50427,2.81821 4.46514,3.04333 2.92852,0.33623 2.93789,0.32121 1.08045,-1.73124 -1.53602,-1.69728 -1.64654,-2.34411 -0.61324,-3.58916 2.84565,-3.4288 7.14497,-0.49759 5.03976,3.43603 -1.86726,3.48903 -8.65528,4.21532 -11.3692,1.21647 z m -4.17462,-14.20302 c -0.38836,-0.62838 -0.23556,-1.61305 0.33954,-2.18816 1.3439,-1.34389 4.47714,-0.17168 3.93038,1.47045 -0.5566,1.67168 -3.38637,2.14732 -4.26992,0.71771 z m -8.48037,-9.1829 c -12.462,-4.1101 -12.53952,-4.12156 -25.49998,-3.7694 -24.020921,0.65269 -32.338219,0.31756 -37.082166,-1.49417 -5.113999,-1.95305 -8.192504,-6.3647405 -6.485463,-9.2940713 0.566827,-0.972691 1.020091,-1.181447 1.037211,-0.477701 0.01685,0.692606 1.268676,1.2499998 2.807321,1.2499998 1.685814,0 4.868609,1.571672 8.10041,4.0000015 4.221481,3.171961 6.182506,3.999221 9.473089,3.996261 l 4.149585,-0.004 -3.249996,-1.98156 c -3.056252,-1.863441 -4.051566,-3.8760635 -2.623216,-5.3044145 0.794,-0.794 6.188222,1.901516 9.064482,4.5295635 1.858669,1.698271 3.461409,1.980521 10.559493,1.859621 11.30984,-0.19266 20.89052,1.29095 31.97905,4.95208 7.63881,2.52213 11.51931,3.16471 22.05074,3.65141 7.02931,0.32486 13.01836,0.97543 13.30902,1.44571 0.29065,0.47029 -5.2356,0.83436 -12.28056,0.80906 -12.25942,-0.044 -13.34537,-0.2229 -25.30902,-4.16865 z"  # noqa
    # }}}
    PATH_CACHE = {}
    VIEWPORT = (400, 500)

    def calculate_margins(self, prefs):
        self.hmargin = int((51 / self.VIEWPORT[0]) * prefs.cover_width)
        self.vmargin = int((83 / self.VIEWPORT[1]) * prefs.cover_height)

    def __call__(self, painter, rect, color_theme, title_block, subtitle_block, footer_block):
        if not self.PATH_CACHE:
            from calibre.utils.speedups import svg_path_to_painter_path
            self.__class__.PATH_CACHE['corner'] = svg_path_to_painter_path(self.CORNER_VECTOR)
        p = painter
        painter.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(QPointF(rect.center()), rect.width())
        g.setColorAt(0, self.color1), g.setColorAt(1, self.color2)
        painter.fillRect(rect, QBrush(g))
        painter.save()
        painter.setWindow(0, 0, *self.VIEWPORT)
        path = self.PATH_CACHE['corner']
        pen = p.pen()
        pen.setColor(self.ccolor1)
        p.setPen(pen)

        def corner():
            b = QBrush(self.ccolor1)
            p.fillPath(path, b)
            p.rotate(90), p.translate(100, -100), p.scale(1, -1), p.translate(-103, -97)
            p.fillPath(path, b)
            p.setWorldTransform(QTransform())
        # Top-left corner
        corner()
        # Top right corner
        p.scale(-1, 1), p.translate(-400, 0), corner()
        # Bottom left corner
        p.scale(1, -1), p.translate(0, -500), corner()
        # Bottom right corner
        p.scale(-1, -1), p.translate(-400, -500), corner()
        for y in (28.4, 471.7):
            p.drawLine(QPointF(160, y), QPointF(240, y))
        for x in (31.3, 368.7):
            p.drawLine(QPointF(x, 155), QPointF(x, 345))
        pen.setWidthF(1.8)
        p.setPen(pen)
        for y in (23.8, 476.7):
            p.drawLine(QPointF(160, y), QPointF(240, y))
        for x in (26.3, 373.7):
            p.drawLine(QPointF(x, 155), QPointF(x, 345))
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


def calibre_cover2(title, author_string='', series_string='', prefs=None, as_qimage=False, logo_path=None):
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
            logo = QImage(logo_path or I('library.png'))
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


def message_image(text, width=500, height=400, font_size=20):
    init_environment()
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(Qt.white)
    p = QPainter(img)
    f = QFont()
    f.setPixelSize(font_size)
    p.setFont(f)
    r = img.rect().adjusted(10, 10, -10, -10)
    p.drawText(r, Qt.AlignJustify | Qt.AlignVCenter | Qt.TextWordWrap, text)
    p.end()
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
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    f = QFont(font_family)
    f.setStyleStrategy(QFont.PreferAntialias)
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
    from PyQt5.Qt import QLabel, QPixmap, QMainWindow, QWidget, QScrollArea, QGridLayout
    from calibre.gui2 import Application
    app = Application([])
    mi = Metadata('Unknown', ['Kovid Goyal', 'John & Doe', 'Author'])
    mi.series = 'A series & styles'
    m = QMainWindow()
    sa = QScrollArea(m)
    w = QWidget(m)
    sa.setWidget(w)
    l = QGridLayout(w)
    w.setLayout(l), l.setSpacing(30)
    scale *= w.devicePixelRatioF()
    labels = []
    for r, color in enumerate(sorted(default_color_themes)):
        for c, style in enumerate(sorted(all_styles())):
            mi.series_index = c + 1
            mi.title = 'An algorithmic cover [%s]' % color
            prefs = override_prefs(cprefs, override_color_theme=color, override_style=style)
            scale_cover(prefs, scale)
            img = generate_cover(mi, prefs=prefs, as_qimage=True)
            img.setDevicePixelRatio(w.devicePixelRatioF())
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
