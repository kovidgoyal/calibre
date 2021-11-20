__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, collections, operator, copy, re, numbers

from qt.core import (
    Qt, QRectF, QFont, QColor, QPixmap, QGraphicsPixmapItem, QGraphicsItem,
    QFontMetrics, QPen, QBrush, QGraphicsRectItem)

from calibre.ebooks.lrf.fonts import LIBERATION_FONT_MAP
from calibre.ebooks.hyphenate import hyphenate_word
from polyglot.builtins import string_or_bytes

WEIGHT_MAP = lambda wt : int((wt/10)-1)
NULL       = lambda a, b: a
COLOR      = lambda a, b: QColor(*a)
WEIGHT     = lambda a, b: WEIGHT_MAP(a)


class PixmapItem(QGraphicsPixmapItem):

    def __init__(self, data, encoding, x0, y0, x1, y1, xsize, ysize):
        p = QPixmap()
        p.loadFromData(data, encoding, Qt.ImageConversionFlag.AutoColor)
        w, h = p.width(), p.height()
        p = p.copy(x0, y0, min(w, x1-x0), min(h, y1-y0))
        if p.width() != xsize or p.height() != ysize:
            p = p.scaled(int(xsize), int(ysize), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        QGraphicsPixmapItem.__init__(self, p)
        self.height, self.width = ysize, xsize
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)

    def resize(self, width, height):
        p = self.pixmap()
        self.setPixmap(p.scaled(int(width), int(height), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.width, self.height = width, height


class Plot(PixmapItem):

    def __init__(self, plot, dpi):
        img = plot.refobj
        xsize, ysize = dpi*plot.attrs['xsize']/720, dpi*plot.attrs['ysize']/720
        x0, y0, x1, y1 = img.x0, img.y0, img.x1, img.y1
        data, encoding = img.data, img.encoding
        PixmapItem.__init__(self, data, encoding, x0, y0, x1, y1, xsize, ysize)


class FontLoader:

    font_map = {
                'Swis721 BT Roman'     : 'Liberation Sans',
                'Dutch801 Rm BT Roman' : 'Liberation Serif',
                'Courier10 BT Roman'   : 'Liberation Mono',
                }

    def __init__(self, font_map, dpi):
        self.face_map = {}
        self.cache = {}
        self.dpi = dpi
        self.face_map = font_map

    def font(self, text_style):
        device_font = text_style.fontfacename in LIBERATION_FONT_MAP
        try:
            if device_font:
                face = self.font_map[text_style.fontfacename]
            else:
                face = self.face_map[text_style.fontfacename]
        except KeyError:  # Bad fontfacename field in LRF
            face = self.font_map['Dutch801 Rm BT Roman']

        sz = text_style.fontsize
        wt = text_style.fontweight
        style = text_style.fontstyle
        font = (face, wt, style, sz,)
        if font in self.cache:
            rfont = self.cache[font]
        else:
            italic = font[2] == QFont.Style.StyleItalic
            rfont = QFont(font[0], int(font[3]), int(font[1]), italic)
            rfont.setPixelSize(int(font[3]))
            rfont.setBold(wt>=69)
            self.cache[font] = rfont
        qfont = rfont
        if text_style.emplinetype != 'none':
            qfont = QFont(rfont)
            qfont.setOverline(text_style.emplineposition == 'before')
            qfont.setUnderline(text_style.emplineposition == 'after')
        return qfont


class Style:
    map = collections.defaultdict(lambda : NULL)

    def __init__(self, style, dpi):
        self.fdpi = dpi/720
        self.update(style.as_dict())

    def update(self, *args, **kwds):
        if len(args) > 0:
            kwds = args[0]
        for attr in kwds:
            setattr(self, attr, self.__class__.map[attr](kwds[attr], self.fdpi))

    def copy(self):
        return copy.copy(self)


class TextStyle(Style):

    map = collections.defaultdict(lambda : NULL,
        fontsize=operator.mul,
        fontwidth=operator.mul,
        fontweight=WEIGHT,
        textcolor=COLOR,
        textbgcolor=COLOR,
        wordspace=operator.mul,
        letterspace=operator.mul,
        baselineskip=operator.mul,
        linespace=operator.mul,
        parindent=operator.mul,
        parskip=operator.mul,
        textlinewidth=operator.mul,
        charspace=operator.mul,
        linecolor=COLOR,
        )

    def __init__(self, style, font_loader, ruby_tags):
        self.font_loader = font_loader
        self.fontstyle   = QFont.Style.StyleNormal
        for attr in ruby_tags:
            setattr(self, attr, ruby_tags[attr])
        Style.__init__(self, style, font_loader.dpi)
        self.emplinetype = 'none'
        self.font = self.font_loader.font(self)

    def update(self, *args, **kwds):
        Style.update(self, *args, **kwds)
        self.font = self.font_loader.font(self)


class BlockStyle(Style):
    map = collections.defaultdict(lambda : NULL,
        bgcolor=COLOR,
        framecolor=COLOR,
        )


class ParSkip:

    def __init__(self, parskip):
        self.height = parskip

    def __str__(self):
        return 'Parskip: '+str(self.height)


class TextBlock:

    class HeightExceeded(Exception):
        pass

    has_content = property(fget=lambda self: self.peek_index < len(self.lines)-1)
    XML_ENTITIES = {
            "apos" : "'",
            "quot" : '"',
            "amp" : "&",
            "lt" : "<",
            "gt" : ">"
    }

    def __init__(self, tb, font_loader, respect_max_y, text_width, logger,
                 opts, ruby_tags, link_activated):
        self.block_id = tb.id
        self.bs, self.ts = BlockStyle(tb.style, font_loader.dpi), \
                            TextStyle(tb.textstyle, font_loader, ruby_tags)
        self.bs.update(tb.attrs)
        self.ts.update(tb.attrs)
        self.lines = collections.deque()
        self.line_length = min(self.bs.blockwidth, text_width)
        self.line_length -= 2*self.bs.sidemargin
        self.line_offset = self.bs.sidemargin
        self.first_line = True
        self.current_style = self.ts.copy()
        self.current_line = None
        self.font_loader, self.logger, self.opts = font_loader, logger, opts
        self.in_link = False
        self.link_activated = link_activated
        self.max_y = self.bs.blockheight if (respect_max_y or self.bs.blockrule.lower() in ('vert-fixed', 'block-fixed')) else sys.maxsize
        self.height = 0
        self.peek_index = -1

        try:
            self.populate(tb.content)
            self.end_line()
        except TextBlock.HeightExceeded:
            pass
            # logger.warning('TextBlock height exceeded, skipping line:\n%s'%(err,))

    def peek(self):
        return self.lines[self.peek_index+1]

    def commit(self):
        self.peek_index += 1

    def reset(self):
        self.peek_index = -1

    def create_link(self, refobj):
        if self.current_line is None:
            self.create_line()
        self.current_line.start_link(refobj, self.link_activated)
        self.link_activated(refobj, on_creation=True)

    def end_link(self):
        if self.current_line is not None:
            self.current_line.end_link()

    def close_valign(self):
        if self.current_line is not None:
            self.current_line.valign = None

    def populate(self, tb):
        self.create_line()
        open_containers = collections.deque()
        self.in_para = False
        for i in tb.content:
            if isinstance(i, string_or_bytes):
                self.process_text(i)
            elif i is None:
                if len(open_containers) > 0:
                    for a, b in open_containers.pop():
                        if callable(a):
                            a(*b)
                        else:
                            setattr(self, a, b)
            elif i.name == 'P':
                open_containers.append((('in_para', False),))
                self.in_para = True
            elif i.name == 'CR':
                if self.in_para:
                    self.end_line()
                    self.create_line()
                else:
                    self.end_line()
                    delta = getattr(self.current_style, 'parskip', 0)
                    if isinstance(self.lines[-1], ParSkip):
                        delta += self.current_style.baselineskip
                    self.lines.append(ParSkip(delta))
                    self.first_line = True
            elif i.name == 'Span':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.update(i.attrs)
            elif i.name == 'CharButton':
                open_containers.append(((self.end_link, []),))
                self.create_link(i.attrs['refobj'])
            elif i.name == 'Italic':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.update(fontstyle=QFont.Style.StyleItalic)
            elif i.name == 'Plot':
                plot = Plot(i, self.font_loader.dpi)
                if self.current_line is None:
                    self.create_line()
                if not self.current_line.can_add_plot(plot):
                    self.end_line()
                    self.create_line()
                self.current_line.add_plot(plot)
            elif i.name in ['Sup', 'Sub']:
                if self.current_line is None:
                    self.create_line()
                self.current_line.valign = i.name
                open_containers.append(((self.close_valign, []),))
            elif i.name == 'Space' and self.current_line is not None:
                self.current_line.add_space(i.attrs['xsize'])
            elif i.name == 'EmpLine':
                if i.attrs:
                    open_containers.append((('current_style', self.current_style.copy()),))
                    self.current_style.update(i.attrs)
            else:
                self.logger.warning('Unhandled TextTag %s'%(i.name,))
                if not i.self_closing:
                    open_containers.append([])

    def end_line(self):
        if self.current_line is not None:
            self.height += self.current_line.finalize(self.current_style.baselineskip,
                                                      self.current_style.linespace,
                                                      self.opts.visual_debug)
            if self.height > self.max_y+10:
                raise TextBlock.HeightExceeded(str(self.current_line))
            self.lines.append(self.current_line)
            self.current_line = None

    def create_line(self):
        line_length = self.line_length
        line_offset = self.line_offset
        if self.first_line:
            line_length -= self.current_style.parindent
            line_offset += self.current_style.parindent
        self.current_line = Line(line_length, line_offset,
                                 self.current_style.linespace,
                                 self.current_style.align,
                                 self.opts.hyphenate, self.block_id)
        self.first_line = False

    def process_text(self, raw):
        for ent, rep in TextBlock.XML_ENTITIES.items():
            raw = raw.replace('&%s;'%ent, rep)
        while len(raw) > 0:
            if self.current_line is None:
                self.create_line()
            pos, line_filled = self.current_line.populate(raw, self.current_style)
            raw = raw[pos:]
            if line_filled:
                self.end_line()
            if not pos:
                break

    def __iter__(self):
        yield from self.lines

    def __str__(self):
        s = ''
        for line in self:
            s += str(line) + '\n'
        return s


class Link(QGraphicsRectItem):
    inactive_brush = QBrush(QColor(0xff, 0xff, 0xff, 0xff))
    active_brush   = QBrush(QColor(0x00, 0x00, 0x00, 0x59))

    def __init__(self, parent, start, stop, refobj, slot):
        QGraphicsRectItem.__init__(self, start, 0, stop-start, parent.height, parent)
        self.refobj = refobj
        self.slot = slot
        self.brush = self.__class__.inactive_brush
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.brush = self.__class__.active_brush
        self.parentItem().update()

    def hoverLeaveEvent(self, event):
        self.brush = self.__class__.inactive_brush
        self.parentItem().update()

    def mousePressEvent(self, event):
        self.hoverLeaveEvent(None)
        self.slot(self.refobj)


class Line(QGraphicsItem):
    whitespace = re.compile(r'\s+')

    def __init__(self, line_length, offset, linespace, align, hyphenate, block_id):
        QGraphicsItem.__init__(self)

        self.line_length, self.offset, self.line_space = line_length, offset, linespace
        self.align, self.hyphenate, self.block_id = align, hyphenate, block_id

        self.tokens = collections.deque()
        self.current_width = 0
        self.length_in_space = 0
        self.height, self.descent, self.width = 0, 0, 0
        self.links = collections.deque()
        self.current_link = None
        self.valign = None
        if not hasattr(self, 'children'):
            self.children = self.childItems

    def start_link(self, refobj, slot):
        self.current_link = [self.current_width, sys.maxsize, refobj, slot]

    def end_link(self):
        if self.current_link is not None:
            self.current_link[1] = self.current_width
            self.links.append(self.current_link)
            self.current_link = None

    def can_add_plot(self, plot):
        return self.line_length - self.current_width >= plot.width

    def add_plot(self, plot):
        self.tokens.append(plot)
        self.current_width += plot.width
        self.height = max(self.height, plot.height)
        self.add_space(6)

    def populate(self, phrase, ts, process_space=True):
        phrase_pos = 0
        processed = False
        matches = self.__class__.whitespace.finditer(phrase)
        font = QFont(ts.font)
        if self.valign is not None:
            font.setPixelSize(font.pixelSize()/1.5)
        fm = QFontMetrics(font)
        single_space_width = fm.horizontalAdvance(' ')
        height, descent = fm.height(), fm.descent()
        for match in matches:
            processed = True
            left, right = match.span()
            if not process_space:
                right = left
            space_width = single_space_width * (right-left)
            word = phrase[phrase_pos:left]
            width = fm.horizontalAdvance(word)
            if self.current_width + width < self.line_length:
                self.commit(word, width, height, descent, ts, font)
                if space_width > 0 and self.current_width + space_width < self.line_length:
                    self.add_space(space_width)
                phrase_pos = right
                continue

            # Word doesn't fit on line
            if self.hyphenate and len(word) > 3:
                tokens = hyphenate_word(word)
                for i in range(len(tokens)-2, -1, -1):
                    word = ''.join(tokens[0:i+1])+'-'
                    width = fm.horizontalAdvance(word)
                    if self.current_width + width < self.line_length:
                        self.commit(word, width, height, descent, ts, font)
                        return phrase_pos + len(word)-1, True
            if self.current_width < 5:  # Force hyphenation as word is longer than line
                for i in range(len(word)-5, 0, -5):
                    part = word[:i] + '-'
                    width = fm.horizontalAdvance(part)
                    if self.current_width + width < self.line_length:
                        self.commit(part, width, height, descent, ts, font)
                        return phrase_pos + len(part)-1, True
            # Failed to add word.
            return phrase_pos, True

        if not processed:
            return self.populate(phrase+' ', ts, False)

        return phrase_pos, False

    def commit(self, word, width, height, descent, ts, font):
        self.tokens.append(Word(word, width, height, ts, font, self.valign))
        self.current_width += width
        self.height = max(self.height, height)
        self.descent = max(self.descent, descent)

    def add_space(self, min_width):
        self.tokens.append(min_width)
        self.current_width += min_width
        self.length_in_space += min_width

    def justify(self):
        delta = self.line_length - self.current_width
        if self.length_in_space > 0:
            frac = 1 + float(delta)/self.length_in_space
            for i in range(len(self.tokens)):
                if isinstance(self.tokens[i], numbers.Number):
                    self.tokens[i] *= frac
            self.current_width = self.line_length

    def finalize(self, baselineskip, linespace, vdebug):
        if self.current_link is not None:
            self.end_link()

        # We justify if line is small and it doesn't have links in it
        # If it has links, justification would cause the boundingrect of the link to
        # be too small
        if self.current_width >= 0.85 * self.line_length and len(self.links) == 0:
            self.justify()

        self.width = float(self.current_width)
        if self.height == 0:
            self.height = baselineskip
        self.height = float(self.height)

        self.vdebug = vdebug

        for link in self.links:
            Link(self, *link)

        return self.height

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget):
        x, y = 0, 0+self.height-self.descent
        if self.vdebug:
            painter.save()
            painter.setPen(QPen(Qt.GlobalColor.yellow, 1, Qt.PenStyle.DotLine))
            painter.drawRect(self.boundingRect())
            painter.restore()
        painter.save()
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        for c in self.children():
            painter.setBrush(c.brush)
            painter.drawRect(c.boundingRect())
        painter.restore()
        painter.save()
        for tok in self.tokens:
            if isinstance(tok, numbers.Number):
                x += tok
            elif isinstance(tok, Word):
                painter.setFont(tok.font)
                if tok.highlight:
                    painter.save()
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                    painter.setBrush(QBrush(Qt.GlobalColor.yellow))
                    painter.drawRect(int(x), 0, tok.width, tok.height)
                    painter.restore()
                painter.setPen(QPen(tok.text_color))
                if tok.valign is None:
                    painter.drawText(int(x), int(y), tok.string)
                elif tok.valign == 'Sub':
                    painter.drawText(int(x+1), int(y+self.descent/1.5), tok.string)
                elif tok.valign == 'Sup':
                    painter.drawText(int(x+1), int(y-2.*self.descent), tok.string)
                x += tok.width
            else:
                painter.drawPixmap(int(x), 0, tok.pixmap())
                x += tok.width
        painter.restore()

    def words(self):
        for w in self.tokens:
            if isinstance(w, Word):
                yield w

    def search(self, phrase):
        tokens = phrase.lower().split()
        if len(tokens) < 1:
            return None

        words = self.words()
        matches = []
        try:
            while True:
                word = next(words)
                word.highlight = False
                if tokens[0] in str(word.string).lower():
                    matches.append(word)
                    for c in range(1, len(tokens)):
                        word = next(words)
                        print(tokens[c], word.string)
                        if tokens[c] not in str(word.string):
                            return None
                        matches.append(word)
                    for w in matches:
                        w.highlight = True
                    return self
        except StopIteration:
            return None

    def getx(self, textwidth):
        if self.align == 'head':
            return self.offset
        if self.align == 'foot':
            return textwidth - self.width
        if self.align == 'center':
            return (textwidth-self.width)/2.

    def __unicode__(self):
        s = ''
        for tok in self.tokens:
            if isinstance(tok, numbers.Number):
                s += ' '
            elif isinstance(tok, Word):
                s += str(tok.string)
        return s

    def __str__(self):
        return str(self).encode('utf-8')


class Word:

    def __init__(self, string, width, height, ts, font, valign):
        self.string, self.width, self.height = string, width, height
        self.font = font
        self.text_color = ts.textcolor
        self.highlight = False
        self.valign = valign


def main(args=sys.argv):
    return 0


if __name__ == '__main__':
    sys.exit(main())
