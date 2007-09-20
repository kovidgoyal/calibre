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

import operator, collections, copy, re

from PyQt4.QtCore import Qt, QByteArray
from PyQt4.QtGui import QGraphicsRectItem, QGraphicsScene, QPen, \
                        QBrush, QColor, QGraphicsSimpleTextItem, QFontDatabase, \
                        QFont, QGraphicsItem

from libprs500.ebooks.lrf.fonts import FONT_MAP
from libprs500.gui2 import qstring_to_unicode
from libprs500.ebooks.hyphenate import hyphenate_word

class Color(QColor):
    def __init__(self, color):
        QColor.__init__(self, color.r, color.g, color.b, 0xff-color.a)

class Pen(QPen):
    def __init__(self, color, width):
        QPen.__init__(self, QBrush(Color(color)), width,
                      (Qt.SolidLine if width > 0 else Qt.NoPen))

WEIGHT_MAP = lambda wt : int((wt/10.)-1)

class FontLoader(object):
    
    def __init__(self, font_map, dpi):
        self.face_map = {}
        self.cache = {}
        self.dpi = dpi
        
        for font in font_map:
            weight = WEIGHT_MAP(800) if 'Bold' in font else WEIGHT_MAP(400)
            style  = QFont.StyleItalic if 'Italic' in font else QFont.StyleNormal
            self.face_map[font] = [font_map[font], weight, style]
            
    def font(self, text_style, face=None, size=None, weight=None, style=QFont.StyleNormal):
        face = self.face_map[text_style.fontfacename if face is None else face]
        sz = text_style.fontsize if size is None else size
        wt = text_style.fontweight if weight is None else weight
        face[1], face[2] = wt, style
        font = tuple(face) + (sz,)
        if font in self.cache:
            return self.cache[font]
        italic = font[2] == QFont.StyleItalic
        qfont = QFont(font[0], font[3], font[1], italic)
        qfont.setPixelSize(font[3])
        self.cache[font] = qfont
        return qfont
        
class ParSkip(object):
    def __init__(self, parskip):
        self.height = parskip
        
    
    
class Line(QGraphicsRectItem):
    whitespace = re.compile(r'\s+')
    
    def __init__(self, offset, linespace, linelength, align, hyphenate):
        QGraphicsRectItem.__init__(self, 0, 0, 0, 0)
        self.offset, self.line_space, self.line_length = offset, linespace, linelength
        self.linepos = 0
        self.align = align
        self.hyphenate = hyphenate
                
    def hyphenate_word(self, word):
        if self.hyphenate:
            tokens = hyphenate_word(word)
            for i in range(len(tokens)-2, -1, -1):
                part = ''.join(tokens[0:i+1])
                rword = QGraphicsSimpleTextItem(part+'-')
                length = rword.boundingRect().width()  
                if length <= self.line_length - self.linepos:
                    return len(part), rword, length
        if self.linepos == 0:
            return self.force_hyphenate_word(word)
        return 0, None, 0
                
    def force_hyphenate_word(self, word):
        for i in range(len(word)-5, 0, -5):
            part = word[:i]
            rword = QGraphicsSimpleTextItem(part+'-')
            length = rword.boundingRect().width()  
            if length <= self.line_length - self.linepos:
                return len(part), rword, length
                
    def populate(self, phrase, font, wordspace):
        phrase_pos = 0
        processed = False
        for match in self.__class__.whitespace.finditer(phrase):
            processed = True
            left, right = match.span()
            if left == 0:
                self.linepos += right*wordspace
                phrase_pos = right
                continue
            word = phrase[phrase_pos:left]
            rword = QGraphicsSimpleTextItem(word, self)
            rword.setFont(font)
            length = rword.boundingRect().width()
            if length > self.line_length - self.linepos:
                break_at, rword, length = self.hyphenate(word)
                if break_at == 0:
                    return phrase_pos
                phrase_pos += break_at            
            else:
                phrase_pos = right
            rword.setParentItem(self)
            rword.setPos(self.linepos, 0)
            self.linepos += length + (right-left)*wordspace
            
            if self.line_length - self.linepos < 15: # Efficiency to prevent excessive hyphenation
                return phrase_pos
            
        if not processed:
            self.populate(phrase+' ', font, 0)
        
    def finalize(self, wordspace, vdebug):
        crect = self.childrenBoundingRect()
        self.width = self.linepos - wordspace
        self.height = crect.height() + self.line_space
        self.setRect(crect)
        if vdebug:
            self.setPen(QPen(Qt.yellow, 1, Qt.DotLine))
        
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
            s += qstring_to_unicode(word.text()) + ' '
        return
    
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
    
    def __init__(self, style, dpi, ruby_tags):
        Style.__init__(self, style, dpi)
        for attr in ruby_tags:
            setattr(self, attr, ruby_tags[attr])
    
class BlockStyle(Style):
    map = collections.defaultdict(lambda : NULL,
        bgcolor          = COLOR,
        framecolor       = COLOR,
        )
    
    
class TextBlock(ContentObject):
    
    has_content = property(fget=lambda self: self.peek_index < len(self.lines)-2)
        
    def __init__(self, tb, font_loader, logger, opts, ruby_tags, parent=None, x=0, y=0):
        ContentObject.__init__(self)
        self.bs, self.ts = BlockStyle(tb.style, font_loader.dpi), \
                            TextStyle(tb.textstyle, font_loader.dpi, ruby_tags)
        self.bs.update(tb.attrs)
        self.ts.update(tb.attrs)
        self.lines = []
        self.line_length = self.bs.blockwidth - 2*self.bs.sidemargin
        self.line_offset = self.bs.sidemargin
        self.first_line = True
        self.current_style = copy.copy(self.ts)
        self.current_line = None
        self.font_loader, self.logger, self.opts = font_loader, logger, opts
        self.current_font = font_loader.font(self.current_style)
        self.create_lines(tb.content)
        if self.current_line:
            self.end_line()
        self.peek_index = -1
        
        
    def peek(self):
        return self.lines[self.peek_index+1]
    
    def commit(self):
        self.peek_index += 1
    
    def reset(self):
        self.peek_index = -1
        
    def create_lines(self, tb):
        for i in tb:
            if i.name == 'CR':
                self.lines.append(ParSkip(self.current_style.parskip))
                self.first_line = True
            elif i.name == 'P':
                self.process_container(i)
                
    def process_container(self, c):
        for i in c:
            if isinstance(i, basestring):
                self.process_text(i)
            elif i.name == 'CR':
                self.end_line()
            elif i.name == 'Plot':
                pass #TODO: Plot
            else:
                self.process_container(i)
                
    def __iter__(self):
        for line in self.lines: yield line
                
    def end_line(self):
        if self.current_line is not None:
            self.lines.append(self.current_line)
            self.current_line.finalize(self.current_style.wordspace, self.opts.visual_debug)
            self.current_line = None
    
    def create_line(self):
        line_length = self.line_length
        line_offset = self.line_offset
        if self.first_line:
            line_length -= self.current_style.parindent
            line_offset += self.current_style.parindent
        self.current_line = Line(line_offset, self.current_style.linespace, 
                                 line_length, self.current_style.align, self.opts.hyphenate)
        self.first_line = False
                
    def process_text(self, raw):
        if len(raw) == 0:
            return
        while True:
            if self.current_line is None:
                self.create_line()
            pos = self.current_line.populate(raw, self.current_font.font, 
                                             self.current_style.wordspace)
            if pos >= len(raw):
                self.end_line()
                break
            raw = raw[pos:]
                
                    
    def __unicode__(self):
        return u'\n'.join(unicode(l) for l in self.lines)
    
    def __str__(self):
        return unicode(self).encode('utf-8')
            
    
def object_factory(container, obj):
    if hasattr(obj, 'name'):
        if obj.name.endswith('TextBlock'):
            return TextBlock(obj, container.font_loader, container.logger, 
                             container.opts, container.ruby_tags)
    return None    

class _Canvas(QGraphicsRectItem):
    
    def __init__(self, font_loader, logger, opts, width=0, height=0, parent=None, x=0, y=0):
        QGraphicsRectItem.__init__(self, x, y, width, height, parent)
        self.font_loader, self.logger, self.opts = font_loader, logger, opts
        self.current_y, self.max_y = 0, height
        self.is_full = False
        pen = QPen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)
        
    def layout_block(self, block, x, y):
        if isinstance(block, TextBlock):
            self.layout_text_block(block, x, y)
            
    def layout_text_block(self, block, x, y):
        textwidth = block.bs.blockwidth - block.bs.sidemargin
        line = block.peek()
        self.max_y = self.boundingRect().height()
        y += block.bs.topskip
        block_consumed = False
        while y + line.height <= self.max_y:
            block.commit()
            if isinstance(line, QGraphicsItem):
                line.setParentItem(self)
                line.setPos(line.getx(textwidth), y)
            y += line.height
            if not block.has_content:
                y += block.bs.footskip
                block_consumed = True
                break
            else:
                line = block.peek()
        self.current_y = y
        self.is_full = not block_consumed
        
        
    
            
    
class Canvas(_Canvas):
    
    def __init__(self, font_loader, canvas, logger, opts, width=0, height=0):
        if hasattr(canvas, 'canvaswidth'):
            width, height = canvas.canvaswidth, canvas.canvasheight
        _Canvas.__init__(self, font_loader, logger, opts, width=width, height=height)
        
        fg = canvas.framecolor
        bg = canvas.bgcolor
        if not opts.visual_debug and canvas.framemode != 'none':
            self.setPen(Pen(fg, canvas.framewidth))
        self.setBrush(QBrush(Color(bg)))
        for po in canvas:
            obj = po.object
            item = object_factory(self, obj)
            if item: 
                self.layout_block(item, po.x, po.y)
                
    def layout_block(self, block, x, y):
        block.reset()
        _Canvas.layout_block(self, block, x, y)

class Header(Canvas):
    def __init__(self, font_loader, header, page_style, logger, opts):
        Canvas.__init__(self, font_loader, header, logger, opts, 
                        page_style.textwidth,  page_style.headheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.blue, 1, Qt.DashLine))    

class Footer(Canvas):
    def __init__(self, font_loader, footer, page_style, logger, opts):
        Canvas.__init__(self, font_loader, footer, logger, opts,  
                        page_style.textwidth, page_style.footheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.blue, 1, Qt.DashLine))    

class Screen(_Canvas):
    
    def __init__(self, font_loader, chapter, odd, logger, opts):
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
            header = chapter.oddheader if odd else chapter.evenheader
        if page_style.footheight > 0:
            footer = chapter.oddfooter if odd else chapter.evenfooter
        if header:
            header = Header(font_loader, header, page_style, logger, opts)
            header.setParentItem(self)
            header.setPos(self.content_x, self.header_y)
        if footer:
            footer = Footer(font_loader, footer, page_style)
            footer.setParentItem(self)
            footer.setPos(self.content_x, self.footer_y)
            
        self.page = None
        
    def set_page(self, page):
        if self.page is not None:
            self.scene().removeItem(self.page)            
        self.page = page
        self.page.setPos(self.content_x, self.text_y)
        self.scene().addItem(self.page)
            
        
class Page(_Canvas):
    
    def __init__(self, font_loader, logger, opts, width, height):
        _Canvas.__init__(self, font_loader, logger, opts, width, height)
        if opts.visual_debug:
            self.setPen(QPen(Qt.cyan, 1, Qt.DashLine))
        
        
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

class Document(QGraphicsScene):
    
    num_of_pages = property(fget=lambda self: sum(self.chapter_layout))
    
    def __init__(self, lrf, logger, opts):
        QGraphicsScene.__init__(self)
        #opts.hyphenate = opts.hyphenate and lrf.doc_info.lower().strip() == 'en'
        self.lrf, self.logger, self.opts = lrf, logger, opts
        self.pages = []
        self.dpi = lrf.device_info.dpi/10.
        self.ruby_tags = dict(**lrf.ruby_tags)
        self.load_fonts()
        self.chapters = []
        self.chapter_layout = None
        self.current_screen = None
        self.current_page = 0
        self.render_doc()
        
        
    def load_fonts(self):
        font_map = {}
        for font in self.lrf.font_map:
            fdata = QByteArray(self.lrf.font_map[font].data)
            id = QFontDatabase.addApplicationFontFromData(fdata)
            font_map[font] = [str(i) for i in QFontDatabase.applicationFontFamilies(id)][0]
        for font in FONT_MAP:
            fdata = QByteArray(FONT_MAP[font].font_data)
            id = QFontDatabase.addApplicationFontFromData(fdata)
            font_map[font] = [str(i) for i in QFontDatabase.applicationFontFamilies(id)][0]
            
        self.font_loader = FontLoader(font_map, self.dpi)
    
    
    def render_chapter(self, chapter):
        oddscreen, evenscreen = Screen(self.font_loader, chapter, True, self.logger, self.opts), \
                                Screen(self.font_loader, chapter, False, self.logger, self.opts)
        pages = []
        width, height = oddscreen.text_width, oddscreen.text_height
        current_page = Page(self.font_loader, self.logger, self.opts, width, height)
        object_to_page_map = {}
        for object in chapter:
            block = object_factory(self, object)
            if block is None:
                continue
            while block.has_content:
                current_page.add_block(block)
                object_to_page_map[object.id] = len(pages)
                if current_page.is_full:
                    pages.append(current_page)
                    current_page = Page(self.font_loader, self.logger, self.opts, width, height)
        if current_page:
            pages.append(current_page)
        self.chapters.append(Chapter(oddscreen, evenscreen, pages, object_to_page_map))    
            
    
    def render_doc(self):
        for pt in self.lrf.page_trees:
            for chapter in pt:
                self.render_chapter(chapter)
        self.chapter_layout = [i.num_of_pages for i in self.chapters]
    
    def show_page(self, num):
        if num < 1 or num > self.num_of_pages:
            return
        it = iter(self.chapters)
        chapter = it.next()
        num_before = 0
        while num > chapter.num_of_pages:
            num_before += chapter.num_of_pages
            chapter =  it.next()
        odd = num%2 == 1
        page = chapter.page(num - num_before)
        screen = chapter.screen(odd)
        
        if self.current_screen is not None and self.current_screen is not screen:
            self.removeItem(self.current_screen)
        self.current_screen = screen
        if self.current_screen.scene() is None:
            self.addItem(self.current_screen)
        
        self.current_screen.set_page(page)
        self.current_page = num
        
    def next(self):
        self.show_page(self.current_page + 1)
        
    def previous(self):
        self.show_page(self.current_page - 1)
        
    def next_by(self, num):
        self.show_page(self.current_page + num)
        
    def previous_by(self, num):
        self.show_page(self.current_page - num)
        
    def show_page_at_percent(self, p):
        num = self.num_of_pages*(p/100.)
        self.show_page(num)
        