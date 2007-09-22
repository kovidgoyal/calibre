##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
''''''

import operator, collections, copy, re, sys

from PyQt4.QtCore import Qt, QByteArray, SIGNAL, QVariant, QUrl
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsScene, QPen, \
                        QBrush, QColor, QGraphicsTextItem, QFontDatabase, \
                        QFont, QGraphicsItem, QGraphicsLineItem, QPixmap, \
                        QGraphicsPixmapItem, QTextCharFormat, QTextFrameFormat, \
                        QTextBlockFormat, QTextCursor, QTextImageFormat, \
                        QTextDocument

from libprs500.ebooks.lrf.fonts import FONT_MAP
from libprs500.gui2 import qstring_to_unicode
from libprs500.ebooks.hyphenate import hyphenate_word
from libprs500.ebooks.BeautifulSoup import Tag
from libprs500.ebooks.lrf.objects import RuledLine as _RuledLine
from libprs500.ebooks.lrf.objects import Canvas as __Canvas

class Color(QColor):
    def __init__(self, color):
        QColor.__init__(self, color.r, color.g, color.b, 0xff-color.a)

class Pen(QPen):
    def __init__(self, color, width):
        QPen.__init__(self, QBrush(Color(color)), width,
                      (Qt.SolidLine if width > 0 else Qt.NoPen))

WEIGHT_MAP = lambda wt : int((wt/10.)-1)

class FontLoader(object):
    
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
        device_font = text_style.fontfacename in FONT_MAP
        if device_font:
            face = self.font_map[text_style.fontfacename]
        else:
            face = self.face_map[text_style.fontfacename]
        
        sz = text_style.fontsize
        wt = text_style.fontweight
        style = text_style.fontstyle
        font = (face, wt, style, sz,)
        if font in self.cache:
            rfont = self.cache[font]
        else:
            italic = font[2] == QFont.StyleItalic             
            rfont = QFont(font[0], font[3], font[1], italic)
            rfont.setPixelSize(font[3])
            rfont.setBold(wt>=69)
            self.cache[font] = rfont
        qfont = rfont
        if text_style.emplinetype != 'none':
            qfont = QFont(rfont)            
            qfont.setOverline(text_style.emplineposition == 'before')
            qfont.setUnderline(text_style.emplineposition == 'after')
        return qfont
        
class ParSkip(object):
    def __init__(self, parskip):
        self.height = parskip
        
    def __str__(self):
        return 'Parskip: '+str(self.height)

class PixmapItem(QGraphicsPixmapItem):
    def __init__(self, data, encoding, x0, y0, x1, y1, xsize, ysize):
        p = QPixmap()
        p.loadFromData(data, encoding, Qt.AutoColor)
        w, h = p.width(), p.height()
        p = p.copy(x0, y0, min(w, x1-x0), min(h, y1-y0))
        if p.width() != xsize or p.height() != ysize:
            p = p.scaled(xsize, ysize, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) 
        QGraphicsPixmapItem.__init__(self, p)
        self.height, self.width = ysize, xsize
        self.setTransformationMode(Qt.SmoothTransformation)
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)


class Plot(PixmapItem):
    
    def __init__(self, plot, dpi):
        img = plot.refobj
        xsize, ysize = dpi*plot.attrs['xsize']/720., dpi*plot.attrs['xsize']/720.
        x0, y0, x1, y1 = img.x0, img.y0, img.x1, img.y1
        data, encoding = img.data, img.encoding
        PixmapItem.__init__(self, data, encoding, x0, y0, x1, y1, xsize, ysize)


class Line(QGraphicsRectItem):
    whitespace = re.compile(r'\s+')
    no_pen = QPen(Qt.NoPen)
    inactive_brush = QBrush(QColor(0x00, 0x00, 0x00, 0x09))
    active_brush   = QBrush(QColor(0x00, 0x00, 0x00, 0x59))
    
    line_map = {
                'none'   : QTextCharFormat.NoUnderline,
                'solid'  : QTextCharFormat.SingleUnderline,
                'dotted' : QTextCharFormat.DotLine,
                'dashed' : QTextCharFormat.DashUnderline,
                'double' : QTextCharFormat.WaveUnderline,
                }
    
    
    def __init__(self, offset, linespace, linelength, align, hyphenate, ts, block_id):
        QGraphicsRectItem.__init__(self, 0, 0, 0, 0)
        self.offset, self.line_space, self.line_length = offset, linespace, linelength
        self.align = align
        self.do_hyphenation = hyphenate
        self.setPen(self.__class__.no_pen)
        self.is_empty = True
        self.highlight_rect = None       
        self.cursor = None
        self.item = None
        self.plot_counter = 0
        self.create_text_item(ts)
        self.block_id = block_id
                
    def hoverEnterEvent(self, event):
        if self.highlight_rect is not None:
            self.highlight_rect.setBrush(self.__class__.active_brush)
        
    def hoverLeaveEvent(self, event):
        if self.highlight_rect is not None:
            self.highlight_rect.setBrush(self.__class__.inactive_brush)
        
    def mousePressEvent(self, event):
        if self.highlight_rect is not None:
            self.hoverLeaveEvent(None)
            self.link[1](self.link[0])
    
    def create_link(self, pos, in_link):
        if not self.acceptsHoverEvents():
            self.setAcceptsHoverEvents(True)
            self.highlight_rect = QGraphicsRectItem(pos, 0, 0, 0, self)
            self.highlight_rect.setCursor(Qt.PointingHandCursor)
            self.link = in_link
            self.link_end = sys.maxint
            
    def end_link(self):
        self.link_end = self.item.boundingRect().width() - self.highlight_rect.boundingRect().x()
    
    def add_plot(self, plot, ts, in_link):
        label='plot%d'%(self.plot_counter,)
        self.plot_counter += 1
        pos = self.item.boundingRect().width()
        self.item.document().addResource(QTextDocument.ImageResource, QUrl(label),
                                         QVariant(plot.pixmap()))
        qif = QTextImageFormat()
        qif.setHeight(plot.height)
        qif.setWidth(plot.width)
        qif.setName(label)
        self.cursor.insertImage(qif, QTextFrameFormat.InFlow)
        if in_link:
            self.create_link(pos, in_link)
        
        
    def can_add_plot(self, plot):
        pos = self.item.boundingRect().width() if self.item is not None else 0
        return self.line_length - pos >= plot.width
    
    def create_text_item(self, ts):
        self.item = QGraphicsTextItem(self)
        self.cursor = QTextCursor(self.item.document())
        f = self.cursor.currentFrame()
        ff = QTextFrameFormat()
        ff.setBorder(0)
        ff.setPadding(0)
        ff.setMargin(0)
        f.setFrameFormat(ff)
        bf = QTextBlockFormat()
        bf.setTopMargin(0)
        bf.setRightMargin(0)
        bf.setBottomMargin(0)
        bf.setRightMargin(0)
        bf.setNonBreakableLines(True)
        self.cursor.setBlockFormat(bf)
        
        
    def build_char_format(self, ts):
        tcf = QTextCharFormat()
        tcf.setFont(ts.font)
        tcf.setVerticalAlignment(ts.valign)
        tcf.setForeground(ts.textcolor)
        tcf.setUnderlineColor(ts.linecolor)
        if ts.emplineposition == 'after':
            tcf.setUnderlineStyle(self.line_map[ts.emplinetype])
        return tcf
    
    def populate(self, phrase, ts, wordspace, in_link):
        phrase_pos = 0
        processed = False
        matches = self.__class__.whitespace.finditer(phrase)
        tcf = self.build_char_format(ts)
        if in_link:
            start = self.item.boundingRect().width()
        for match in matches:
            processed = True
            left, right = match.span()
            if wordspace == 0:
                right = left
            word = phrase[phrase_pos:right]
            self.cursor.insertText(word, tcf)
            if self.item.boundingRect().width() > self.line_length:
                self.cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor,
                                         right-left)
                self.cursor.removeSelectedText()
                if self.item.boundingRect().width() <= self.line_length:
                    if in_link: self.create_link(start, in_link)
                    return right, True
                self.cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor,
                                         left-phrase_pos)
                self.cursor.removeSelectedText()
                if self.do_hyphenation:
                    tokens = hyphenate_word(word)
                    for i in range(len(tokens)-2, -1, -1):
                        part = ''.join(tokens[0:i+1])
                        self.cursor.insertText(part+'-', tcf)
                        if self.item.boundingRect().width() <= self.line_length:
                            if in_link: self.create_link(start, in_link)
                            return phrase_pos + len(part), True
                        self.cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor,
                                         len(part)+1)
                        self.cursor.removeSelectedText()
                if self.cursor.position() < 1: # Force hyphenation as word is longer than line
                    for i in range(len(word)-5, 0, -5):
                        part = word[:i]
                        self.cursor.insertText(part+'-', tcf)
                        if self.item.boundingRect().width() <= self.line_length:
                            if in_link: self.create_link(start, in_link)
                            return phrase_pos + len(part), True
                        self.cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor,
                                         len(part)+1)
                        self.cursor.removeSelectedText()
                return phrase_pos, True
                        
            if in_link: self.create_link(start, in_link)
            phrase_pos = right
                
        if not processed:
            return self.populate(phrase+' ', ts, 0, in_link)
            
        return phrase_pos, False
            
    
        
    def finalize(self, wordspace, vdebug):
        crect = self.childrenBoundingRect()
        self.width = crect.width() - wordspace
        self.height = crect.height() + self.line_space
        self.setRect(crect)
        
        if vdebug:
            self.setPen(QPen(Qt.yellow, 1, Qt.DotLine))
        if self.highlight_rect is not None:
            x = self.highlight_rect.boundingRect().x()
            if self.link_end == sys.maxint:
                self.link_end = crect.width()-x
            self.highlight_rect.setRect(crect)
            erect = self.highlight_rect.boundingRect()
            erect.setX(x)
            erect.setWidth(self.link_end)
            self.highlight_rect.setRect(erect)
            self.highlight_rect.setBrush(self.__class__.inactive_brush)
            self.highlight_rect.setZValue(-1)
            self.highlight_rect.setPen(self.__class__.no_pen)
        
        return self.height
        
    def getx(self, textwidth):
        if self.align == 'head':
            return self.offset
        if self.align == 'foot':
            return textwidth - self.width
        if self.align == 'center':        
            return (textwidth-self.width)/2.
        
    def __unicode__(self):
        s = u''
        for word in self.children():
            if not hasattr(word, 'toPlainText'):
                continue
            s += qstring_to_unicode(word.toPlainText())
        return s
    
    def __str__(self):
        return unicode(self).encode('utf-8')
        

class ContentObject(object):
    
    has_content = True
            
    def reset(self):
        self.has_content = True


NULL   = lambda a, b: a
COLOR  = lambda a, b: QColor(*a)
WEIGHT = lambda a, b: WEIGHT_MAP(a)

class Style(object):
    map = collections.defaultdict(lambda : NULL)
    
    def __init__(self, style, dpi):
        self.fdpi = dpi/720.
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
        fontsize         = operator.mul,
        fontwidth        = operator.mul,
        fontweight       = WEIGHT,
        textcolor        = COLOR,
        textbgcolor      = COLOR,
        wordspace        = operator.mul,
        letterspace      = operator.mul,
        baselineskip     = operator.mul,
        linespace        = operator.mul,
        parindent        = operator.mul,
        parskip          = operator.mul,
        textlinewidth    = operator.mul,
        charspace        = operator.mul,
        linecolor        = COLOR, 
        )
    
    def __init__(self, style, font_loader, ruby_tags):
        self.font_loader = font_loader
        self.fontstyle   = QFont.StyleNormal
        self.valign      = QTextCharFormat.AlignBottom
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
        bgcolor          = COLOR,
        framecolor       = COLOR,
        )
    

class TextBlock(ContentObject):
    
    has_content = property(fget=lambda self: self.peek_index < len(self.lines)-1)
    XML_ENTITIES = dict(zip(Tag.XML_SPECIAL_CHARS_TO_ENTITIES.values(), Tag.XML_SPECIAL_CHARS_TO_ENTITIES.keys())) 
    XML_ENTITIES["quot"] = '"'
    
    class HeightExceeded(Exception): 
        pass

    
    def __init__(self, tb, font_loader, respect_max_y, text_width, logger, 
                 opts, ruby_tags, link_activated, 
                 parent=None, x=0, y=0):
        ContentObject.__init__(self)
        self.block_id = tb.id
        self.bs, self.ts = BlockStyle(tb.style, font_loader.dpi), \
                            TextStyle(tb.textstyle, font_loader, ruby_tags)
        self.bs.update(tb.attrs)
        self.ts.update(tb.attrs)
        self.lines = []
        self.line_length = min(self.bs.blockwidth, text_width)
        self.line_length -= 2*self.bs.sidemargin
        self.line_offset = self.bs.sidemargin
        self.first_line = True
        self.current_style = self.ts.copy()
        self.current_line = None
        self.font_loader, self.logger, self.opts = font_loader, logger, opts
        self.in_link = False
        self.link_activated = link_activated
        self.max_y = self.bs.blockheight if (respect_max_y or self.bs.blockrule.lower() in ('vert-fixed', 'block-fixed')) else sys.maxint
        self.height = 0
        try:
            if self.max_y > 0:
                self.populate(tb.content)
                self.end_line()
        except TextBlock.HeightExceeded:
            logger.warning('TextBlock height exceeded, truncating.')
        self.peek_index = -1
        
        
        
    def peek(self):
        return self.lines[self.peek_index+1]
    
    def commit(self):
        self.peek_index += 1
    
    def reset(self):
        self.peek_index = -1
        
    def end_link(self):
        self.link_activated(self.in_link[0], on_creation=True)
        self.in_link = False
    
    def populate(self, tb):
        self.create_line()
        open_containers = collections.deque()
        self.in_para = False
        for i in tb.content:
            if isinstance(i, basestring):
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
                    delta = self.current_style.parskip
                    if isinstance(self.lines[-1], ParSkip):
                        delta += self.current_style.baselineskip
                    self.lines.append(ParSkip(delta))
                    self.first_line = True
            elif i.name == 'Span':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.update(i.attrs)                
            elif i.name == 'CharButton':
                open_containers.append(((self.end_link, []),))
                self.in_link = (i.attrs['refobj'], self.link_activated)
            elif i.name == 'Italic':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.update(fontstyle=QFont.StyleItalic)
            elif i.name == 'Plot':
                plot = Plot(i, self.font_loader.dpi)
                if self.current_line is None:
                    self.create_line()
                if not self.current_line.can_add_plot(plot):
                    self.end_line()
                    self.create_line()
                self.current_line.add_plot(plot, self.current_style, self.in_link)
            elif i.name == 'Sup':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.valign=QTextCharFormat.AlignSuperScript
            elif i.name == 'Sub':
                open_containers.append((('current_style', self.current_style.copy()),))
                self.current_style.valign=QTextCharFormat.AlignSubScript
            elif i.name == 'EmpLine':
                if i.attrs:
                    open_containers.append((('current_style', self.current_style.copy()),))
                    self.current_style.update(i.attrs)
            else:
                self.logger.warning('Unhandled TextTag %s'%(i.name,))
                if not i.self_closing:
                    open_containers.append([])
                
    def __iter__(self):
        for line in self.lines: yield line
                
    def end_line(self):
        if self.current_line is not None:
            self.height += self.current_line.finalize(self.current_style.wordspace, self.opts.visual_debug)
            if self.height > self.max_y+10:
                raise TextBlock.HeightExceeded
            self.lines.append(self.current_line)            
            self.current_line = None
    
    def create_line(self):
        line_length = self.line_length
        line_offset = self.line_offset
        if self.first_line:
            line_length -= self.current_style.parindent
            line_offset += self.current_style.parindent
        self.current_line = Line(line_offset, self.current_style.linespace, 
                                 line_length, self.current_style.align, 
                                 self.opts.hyphenate, self.current_style, self.block_id)
        self.first_line = False
                
    def process_text(self, raw):
        for ent, rep in TextBlock.XML_ENTITIES.items():
            raw = raw.replace(u'&%s;'%ent, rep)
        while len(raw) > 0:
            if self.current_line is None:
                self.create_line()
            pos, line_filled = self.current_line.populate(raw, self.current_style, 
                                             self.current_style.wordspace, self.in_link)
            raw = raw[pos:]
            if line_filled:
                self.end_line()

                    
    def __unicode__(self):
        return u'\n'.join(unicode(l) for l in self.lines)
    
    def __str__(self):
        
        return '<TextBlock>\n'+unicode(self).encode('utf-8')+'\n</TextBlock>'
            

class RuledLine(QGraphicsLineItem, ContentObject):
    
    map = {'solid': Qt.SolidLine, 'dashed': Qt.DashLine, 'dotted': Qt.DotLine, 'double': Qt.DashDotLine}
    
    def __init__(self, rl):
        QGraphicsLineItem.__init__(self, 0, 0, rl.linelength, 0)
        ContentObject.__init__(self)
        self.setPen(QPen(COLOR(rl.linecolor, None), rl.linewidth, ))


class ImageBlock(PixmapItem, ContentObject):
    
    def __init__(self, obj):
        ContentObject.__init__(self)
        x0, y0, x1, y1 = obj.attrs['x0'], obj.attrs['y0'], obj.attrs['x1'], obj.attrs['y1']
        xsize, ysize, refstream = obj.attrs['xsize'], obj.attrs['ysize'], obj.refstream
        data, encoding = refstream.stream, refstream.encoding
        PixmapItem.__init__(self, data, encoding, x0, y0, x1, y1, xsize, ysize)
        self.block_id = obj.id
        

def object_factory(container, obj, respect_max_y=False):
    if hasattr(obj, 'name'):
        if obj.name.endswith('TextBlock'):
            return TextBlock(obj, container.font_loader, respect_max_y, container.text_width,
                             container.logger, 
                             container.opts, container.ruby_tags, container.link_activated)
        elif obj.name.endswith('ImageBlock'):
            return ImageBlock(obj)
    elif isinstance(obj, _RuledLine):
        return RuledLine(obj)
    elif isinstance(obj, __Canvas):
        return Canvas(container.font_loader, obj, container.logger, container.opts, 
                      container.ruby_tags, container.link_activated)        
    return None    

class _Canvas(QGraphicsRectItem):
    
    def __init__(self, font_loader, logger, opts, width=0, height=0, parent=None, x=0, y=0):
        QGraphicsRectItem.__init__(self, x, y, width, height, parent)
        self.font_loader, self.logger, self.opts = font_loader, logger, opts
        self.current_y, self.max_y, self.max_x = 0, height, width
        self.is_full = False
        pen = QPen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)
        
    def layout_block(self, block, x, y):
        if isinstance(block, TextBlock):
            self.layout_text_block(block, x, y)
        elif isinstance(block, RuledLine):
            self.layout_ruled_line(block, x, y)
        elif isinstance(block, ImageBlock):
            self.layout_image_block(block, x, y)
        elif isinstance(block, Canvas):
            self.layout_canvas(block, x, y)
            
    def layout_canvas(self, canvas, x, y):
        canvas.setParentItem(self)
        canvas.setPos(x, y)
        canvas.has_content = False
        oy = self.current_y
        for block, x, y in canvas.items:
            self.layout_block(block, x, oy+y)
        self.current_y = oy + canvas.max_y
        
    
    def layout_text_block(self, block, x, y):
        textwidth = block.bs.blockwidth - block.bs.sidemargin
        if block.max_y == 0 or not block.lines: # Empty block skipping
            self.is_full = False
            return
        line = block.peek()
        y += block.bs.topskip
        block_consumed = False
        while y + line.height <= self.max_y:
            block.commit()
            if isinstance(line, QGraphicsItem):
                line.setParentItem(self)
                line.setPos(x + line.getx(textwidth), y)
            y += line.height
            if not block.has_content:
                y += block.bs.footskip
                block_consumed = True
                break
            else:
                line = block.peek()
        self.current_y = y
        self.is_full = not block_consumed
        
    def layout_ruled_line(self, rl, x, y):
        br = rl.boundingRect()
        rl.setParentItem(self)
        rl.setPos(x, y+1)
        self.current_y = y + br.height() + 1
        self.is_full = y > self.max_y-5
        rl.has_content = False 
             
    def layout_image_block(self, ib, x, y):
        if self.current_y + ib.height > self.max_y-y and self.current_y < 5:
            self.is_full = True
        else:
            br = ib.boundingRect()
            ib.setParentItem(self)
            ib.setPos(x, y)
            self.current_y = y + br.height()
            self.is_full = y > self.max_y-5
            ib.has_content = False
            
            
    
class Canvas(_Canvas, ContentObject):
    
    def __init__(self, font_loader, canvas, logger, opts, ruby_tags, link_activated, width=0, height=0):
        if hasattr(canvas, 'canvaswidth'):
            width, height = canvas.canvaswidth, canvas.canvasheight
        _Canvas.__init__(self, font_loader, logger, opts, width=width, height=height)
        self.block_id = canvas.id
        self.ruby_tags = ruby_tags
        self.link_activated = link_activated
        self.text_width = width
        fg = canvas.framecolor
        bg = canvas.bgcolor
        if not opts.visual_debug and canvas.framemode != 'none':
            self.setPen(Pen(fg, canvas.framewidth))
        self.setBrush(QBrush(Color(bg)))
        self.items = []
        for po in canvas:
            obj = po.object
            item = object_factory(self, obj, respect_max_y=True)
            if item:
                self.items.append((item, po.x, po.y))
                
    def layout_block(self, block, x, y):
        block.reset()
        _Canvas.layout_block(self, block, x, y)

class Header(Canvas):
    def __init__(self, font_loader, header, page_style, logger, opts, ruby_tags, link_activated):
        Canvas.__init__(self, font_loader, header, logger, opts, ruby_tags, link_activated,
                        page_style.textwidth,  page_style.headheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.blue, 1, Qt.DashLine))    

class Footer(Canvas):
    def __init__(self, font_loader, footer, page_style, logger, opts, ruby_tags, link_activated):
        Canvas.__init__(self, font_loader, footer, logger, opts, ruby_tags, link_activated,
                        page_style.textwidth, page_style.footheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.blue, 1, Qt.DashLine))    

class Screen(_Canvas):
    
    def __init__(self, font_loader, chapter, odd, logger, opts, ruby_tags, link_activated):
        self.logger, self.opts = logger, opts
        page_style = chapter.style
        sidemargin = page_style.oddsidemargin if odd else page_style.evensidemargin
        width = 2*sidemargin + page_style.textwidth
        self.content_x = 0 + sidemargin
        self.text_width = page_style.textwidth
        self.header_y = page_style.topmargin
        
        self.text_y = self.header_y + page_style.headheight + page_style.headsep
        self.text_height = page_style.textheight
        self.footer_y = self.text_y + self.text_height + (page_style.footspace - page_style.footheight)
        
        _Canvas.__init__(self, font_loader, logger, opts, width=width, height=self.footer_y+page_style.footheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.red, 1, Qt.SolidLine))
        header = footer = None
        if page_style.headheight > 0:
            try:
                header = chapter.oddheader if odd else chapter.evenheader
            except AttributeError:
                pass
        if page_style.footheight > 0:
            try:
                footer = chapter.oddfooter if odd else chapter.evenfooter
            except AttributeError:
                pass
        if header:
            header = Header(font_loader, header, page_style, logger, opts, ruby_tags, link_activated)
            self.layout_canvas(header, self.content_x, self.header_y)
        if footer:
            footer = Footer(font_loader, footer, page_style, logger, opts, ruby_tags, link_activated)
            self.layout_canvas(footer, self.content_x, self.header_y)
            
        self.page = None
        
    def set_page(self, page):
        if self.page is not None and self.page.scene():
            self.scene().removeItem(self.page)       
        self.page = page
        self.page.setPos(self.content_x, self.text_y)
        self.scene().addItem(self.page)
        
    def remove(self):
        if self.scene():
            if self.page is not None and self.page.scene():
                self.scene().removeItem(self.page)
            self.scene().removeItem(self)
            
        
class Page(_Canvas):
    
    def __init__(self, font_loader, logger, opts, width, height):
        _Canvas.__init__(self, font_loader, logger, opts, width, height)
        if opts.visual_debug:
            self.setPen(QPen(Qt.cyan, 1, Qt.DashLine))
            
    def id(self):
        for child in self.children():
            if hasattr(child, 'block_id'):
                return child.block_id
        
    def add_block(self, block):
        self.layout_block(block, 0, self.current_y)
        
    
class Chapter(object):
    
    num_of_pages = property(fget=lambda self: len(self.pages))
        
    def __init__(self, oddscreen, evenscreen, pages, object_to_page_map):
        self.oddscreen, self.evenscreen, self.pages, self.object_to_page_map = \
            oddscreen, evenscreen, pages, object_to_page_map
            
    def page_of_object(self, id):
        return self.object_to_page_map[id]
    
    def page(self, num):
        return self.pages[num-1]
    
    def screen(self, odd):
        return self.oddscreen if odd else self.evenscreen

class History(collections.deque):
    
    def __init__(self):
        collections.deque.__init__(self)
        self.pos = 0
        
    def back(self):
        if self.pos - 1 < 0: return None
        self.pos -= 1
        return self[self.pos]
    
    def forward(self):
        if self.pos + 1 >= len(self): return None
        self.pos += 1
        return self[self.pos]
    
    def add(self, item):
        while len(self) > self.pos+1:
            self.pop()
        self.append(item)
        self.pos += 1
            
        

class Document(QGraphicsScene):
    
    num_of_pages = property(fget=lambda self: sum(self.chapter_layout))
    
    def __init__(self, logger, opts):
        QGraphicsScene.__init__(self)
        self.logger, self.opts = logger, opts
        self.pages = []
        self.chapters = []
        self.chapter_layout = None
        self.current_screen = None
        self.current_page = 0
        self.link_map = {}
        self.chapter_map = {}
        self.history = History()
    
    def page_of(self, oid):
        for chapter in self.chapters:
            if oid in chapter.object_to_page_map:
                return  chapter.object_to_page_map[oid]
    
    def get_page_num(self, chapterid, objid):
        cnum = self.chapter_map[chapterid]
        page = self.chapters[cnum].object_to_page_map[objid]
        return sum(self.chapter_layout[:cnum])+page        
    
    def add_to_history(self):
        page = self.chapter_page(self.current_page)[1]
        page_id = page.id()
        if page_id is not None:
            self.history.add(page_id)
    
    def link_activated(self, objid, on_creation=None):
        if on_creation is None:
            cid, oid = self.link_map[objid]
            self.add_to_history()
            page = self.get_page_num(cid, oid)
            self.show_page(page) 
        else:
            jb = self.objects[objid]
            self.link_map[objid] = (jb.refpage, jb.refobj)
            
    def back(self):
        oid = self.history.back()
        if oid is not None:
            page = self.page_of(oid)
            self.show_page(page)
        
    def forward(self):
        oid = self.history.forward()
        if oid is not None:
            page = self.page_of(oid)
            self.show_page(page)
            
    
    def load_fonts(self, lrf):
        font_map = {}
        for font in lrf.font_map:
            fdata = QByteArray(lrf.font_map[font].data)
            id = QFontDatabase.addApplicationFontFromData(fdata)
            font_map[font] = [str(i) for i in QFontDatabase.applicationFontFamilies(id)][0]
        
        from libprs500.ebooks.lrf.fonts.liberation import LiberationMono_BoldItalic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_BoldItalic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationMono_Italic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Italic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSerif_Bold
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Bold.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSans_BoldItalic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_BoldItalic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationMono_Regular
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Regular.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSans_Italic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Italic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSerif_Regular
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Regular.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSerif_Italic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_Italic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSans_Bold
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Bold.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationMono_Bold
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationMono_Bold.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSerif_BoldItalic
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSerif_BoldItalic.font_data))
        from libprs500.ebooks.lrf.fonts.liberation import LiberationSans_Regular
        QFontDatabase.addApplicationFontFromData(QByteArray(LiberationSans_Regular.font_data))
        
            
        self.font_loader = FontLoader(font_map, self.dpi)
    
    
    def render_chapter(self, chapter, lrf):
        oddscreen, evenscreen = Screen(self.font_loader, chapter, True, self.logger, self.opts, self.ruby_tags, self.link_activated), \
                                Screen(self.font_loader, chapter, False, self.logger, self.opts, self.ruby_tags, self.link_activated)
        pages = []
        width, height = oddscreen.text_width, oddscreen.text_height
        current_page = Page(self.font_loader, self.logger, self.opts, width, height)
        object_to_page_map = {}
        for object in chapter:
            self.text_width = width
            block = object_factory(self, object)
            if block is None:
                continue
            while block.has_content:
                current_page.add_block(block)
                object_to_page_map[object.id] = len(pages) + 1
                if current_page.is_full:
                    pages.append(current_page)
                    current_page = Page(self.font_loader, self.logger, self.opts, width, height)
        if current_page:
            pages.append(current_page)
        self.chapters.append(Chapter(oddscreen, evenscreen, pages, object_to_page_map))
        self.chapter_map[chapter.id] = len(self.chapters)-1    
            
    
    def render(self, lrf):
        self.dpi = lrf.device_info.dpi/10.
        self.ruby_tags = dict(**lrf.ruby_tags)
        self.load_fonts(lrf)
        self.objects = lrf.objects
        
        num_chaps = 0
        for pt in lrf.page_trees:
            for chapter in pt:
                num_chaps += 1
        self.emit(SIGNAL('chapter_rendered(int)'), num_chaps)
        
        for pt in lrf.page_trees:
            for chapter in pt:
                self.render_chapter(chapter, lrf)
                self.emit(SIGNAL('chapter_rendered(int)'), -1)
        self.chapter_layout = [i.num_of_pages for i in self.chapters]
        self.objects = None
    
    def chapter_page(self, num):
        for chapter in self.chapters:
            if num <= chapter.num_of_pages:
                break
            num -= chapter.num_of_pages
        return chapter, chapter.page(num)
    
    def show_page(self, num):
        if num < 1 or num > self.num_of_pages or num == self.current_page:
            return
        odd = num%2 == 1
        self.current_page = num
        chapter, page = self.chapter_page(num)
        screen = chapter.screen(odd)
        
        if self.current_screen is not None and self.current_screen is not screen:
            self.current_screen.remove()
        self.current_screen = screen
        if self.current_screen.scene() is None:
            self.addItem(self.current_screen)
        
        self.current_screen.set_page(page)
        self.emit(SIGNAL('page_changed(PyQt_PyObject)'), self.current_page)
        
        
    def next(self):
        self.next_by(1)
        
    def previous(self):
        self.previous_by(1)
        
    def next_by(self, num):
        self.show_page(self.current_page + num)
        
    def previous_by(self, num):
        self.show_page(self.current_page - num)
        
    def show_page_at_percent(self, p):
        num = self.num_of_pages*(p/100.)
        self.show_page(num)
        
