#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import namedtuple
from contextlib import contextmanager
from math import ceil
from future_builtins import map
from itertools import chain

from PyQt5.Qt import (
    QImage, Qt, QFont, QPainter, QPointF, QTextLayout, QTextOption,
    QFontMetrics, QTextCharFormat
)

from calibre import force_unicode
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import ensure_app, config, load_builtin_fonts
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.config import JSONConfig

# Default settings {{{
cprefs = JSONConfig('cover_generation')
cprefs.defaults['title_font_size'] = 60  # px
cprefs.defaults['subtitle_font_size'] = 40  # px
cprefs.defaults['footer_font_size'] = 60  # px
cprefs.defaults['cover_width'] = 600  # px
cprefs.defaults['cover_height'] = 800  # px
cprefs.defaults['title_font_family'] = 'Liberation Serif'
cprefs.defaults['subtitle_font_family'] = 'Liberation Sans'
cprefs.defaults['footer_font_family'] = 'Liberation Sans'
cprefs.defaults['title_template'] = '<b>{title}'
cprefs.defaults['subtitle_template'] = '''{series:'test($, strcat("<i>", $, "</i> - ", raw_field("formatted_series_index")), "")'}'''
cprefs.defaults['footer_template'] = '''program:
# Show at most two authors, on separate lines.
authors = field('authors');
num = count(authors, ' & ');
authors = cmp(num, 2, authors, authors, sublist(authors, 0, 2, ' & '));
authors = re(authors, ' & ', '<br>');
re(authors, '&&', '&')
'''
Prefs = namedtuple('Prefs', ' '.join(sorted(cprefs.defaults)))
# }}}

# Draw text {{{
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

    def __init__(self, text='', width=0, font=None, img=None, max_height=100):
        self.layouts = []
        self._position = 0, 0
        self.leading = 0
        for text in text.split('<br>') if text else ():
            text, formats = parse_text_formatting(text)
            l = QTextLayout(text, font, img)
            l.setAdditionalFormats(formats)
            to = QTextOption(Qt.AlignHCenter | Qt.AlignTop)
            to.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            l.setTextOption(to)

            fm = QFontMetrics(font, img)
            l.beginLayout()
            height, leading = 0, fm.leading()
            while height + 3*leading < max_height:
                line = l.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(width)
                height += leading
                line.setPosition(QPointF(0, height))
                height += line.height()
            max_height -= height
            l.endLayout()
            if self.layouts:
                self.layouts.append(leading)
            else:
                self._position = l.position().x(), l.position().y()
            self.layouts.append(l)

    @property
    def height(self):
        return int(ceil(sum(l if isinstance(l, (int, float)) else l.boundingRect().height() for l in self.layouts)))

    @dynamic_property
    def position(self):
        def fget(self):
            return self._position
        def fset(self, (x, y)):
            self._position = x, y
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
                l.draw(painter, QPointF())

def layout_text(prefs, img, title, subtitle, footer, max_height, hmargin=50, vmargin=50):
    width = img.width() - 2 * hmargin
    title_font = QFont(prefs.title_font_family)
    title_font.setPixelSize(prefs.title_font_size)
    title_block = Block(title, width, title_font, img, max_height)
    title_block.position = hmargin, vmargin
    subtitle_block = Block()
    if subtitle:
        subtitle_font = QFont(prefs.subtitle_font_family)
        subtitle_font.setPixelSize(prefs.subtitle_font_size)
        gap = 2 * title_block.leading
        mh = max_height - title_block.height - gap
        subtitle_block = Block(subtitle, width, subtitle_font, img, mh)
        subtitle_block.position = hmargin, title_block.position[0] + title_block.height + gap

    footer_font = QFont(prefs.footer_font_family)
    footer_font.setPixelSize(prefs.footer_font_size)
    footer_block = Block(footer, width, footer_font, img, max_height)
    footer_block.position = hmargin, img.height() - vmargin - footer_block.height

    return title_block, subtitle_block, footer_block

# }}}

# Format text using templates {{{
def fill_background(prefs, img):
    img.fill(Qt.white)

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

def generate_cover(mi, prefs=None):
    ensure_app()
    load_builtin_fonts()
    prefs = prefs or cprefs
    prefs = {k:prefs.get(k) for k in cprefs.defaults}
    prefs = Prefs(**prefs)
    title, subtitle, footer = format_text(mi, prefs)
    img = QImage(prefs.cover_width, prefs.cover_height, QImage.Format_ARGB32)
    fill_background(prefs, img)
    hmargin = vmargin = 50
    title_block, subtitle_block, footer_block = layout_text(
        prefs, img, title, subtitle, footer, img.height() // 3, hmargin, vmargin)
    p = QPainter(img)
    for block in (title_block, subtitle_block, footer_block):
        block.draw(p)
    p.end()
    return img

def test():
    from PyQt5.Qt import QLabel, QApplication, QPixmap, QMainWindow
    from calibre.ebooks.metadata.book.base import Metadata
    app = QApplication([])
    mi = Metadata('Test title for מתכוני מיצים', ['Author One', 'Author A. Two', 'Author'])
    mi.series = 'A Series of Tests'
    mi.series_index = 3
    img = generate_cover(mi)
    l = QLabel()
    l.setPixmap(QPixmap.fromImage(img))
    m = QMainWindow()
    m.setCentralWidget(l)
    m.show()
    app.exec_()

if __name__ == '__main__':
    test()
