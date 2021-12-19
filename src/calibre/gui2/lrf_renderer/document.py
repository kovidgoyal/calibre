__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import collections, itertools, glob

from qt.core import (
    Qt, QByteArray, pyqtSignal, QGraphicsRectItem, QGraphicsScene, QPen,
    QBrush, QColor, QFontDatabase, QGraphicsItem, QGraphicsLineItem)

from calibre.gui2.lrf_renderer.text import TextBlock, FontLoader, COLOR, PixmapItem
from calibre.ebooks.lrf.objects import RuledLine as _RuledLine
from calibre.ebooks.lrf.objects import Canvas as __Canvas


class Color(QColor):

    def __init__(self, color):
        QColor.__init__(self, color.r, color.g, color.b, 0xff-color.a)


class Pen(QPen):

    def __init__(self, color, width):
        QPen.__init__(self, QBrush(Color(color)), width,
                      (Qt.PenStyle.SolidLine if width > 0 else Qt.PenStyle.NoPen))


class ContentObject:

    has_content = True

    def reset(self):
        self.has_content = True


class RuledLine(QGraphicsLineItem, ContentObject):

    map = {'solid': Qt.PenStyle.SolidLine, 'dashed': Qt.PenStyle.DashLine, 'dotted': Qt.PenStyle.DotLine, 'double': Qt.PenStyle.DashDotLine}

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
                             container.logger, container.opts, container.ruby_tags,
                             container.link_activated)
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
        pen.setStyle(Qt.PenStyle.NoPen)
        self.setPen(pen)
        if not hasattr(self, 'children'):
            self.children = self.childItems

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
        if canvas.max_y + y > self.max_y and y > 0:
            self.is_full = True
            return
        canvas.setParentItem(self)
        canvas.setPos(x, y)
        canvas.has_content = False
        canvas.put_objects()
        self.current_y += canvas.max_y

    def layout_text_block(self, block, x, y):
        textwidth = block.bs.blockwidth - block.bs.sidemargin
        if block.max_y == 0 or not block.lines:  # Empty block skipping
            self.is_full = False
            return
        line = block.peek()
        y += block.bs.topskip
        block_consumed = False
        line.height = min(line.height, self.max_y-block.bs.topskip)  # LRF files from TOR have Plot elements with their height set to 800
        while y + line.height <= self.max_y:
            block.commit()
            if isinstance(line, QGraphicsItem):
                line.setParentItem(self)
                line.setPos(x + line.getx(textwidth), y)
                y += line.height + line.line_space
            else:
                y += line.height
            if not block.has_content:
                try:
                    y += block.bs.footskip
                except AttributeError:  # makelrf generates BlockStyles without footskip
                    pass
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
        mw, mh = self.max_x - x, self.max_y - y
        if self.current_y + ib.height > self.max_y-y and self.current_y > 5:
            self.is_full = True
        else:
            if ib.width > mw or ib.height > mh:
                ib.resize(mw, mh)
            br = ib.boundingRect()
            max_height = min(br.height(), self.max_y-y)
            max_width  = min(br.width(), self.max_x-x)
            if br.height() > max_height or br.width() > max_width:
                p = ib.pixmap()
                ib.setPixmap(p.scaled(int(max_width), int(max_height), Qt.AspectRatioMode.IgnoreAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
                br = ib.boundingRect()
            ib.setParentItem(self)
            ib.setPos(x, y)
            self.current_y = y + br.height()
            self.is_full = y > self.max_y-5
            ib.has_content = False
            if ib.block_id == 54:
                print()
                print(ib.block_id, ib.has_content, self.is_full)
                print(self.current_y, self.max_y, y, br.height())
                print()

    def search(self, phrase):
        matches = []
        for child in self.children():
            if hasattr(child, 'search'):
                res = child.search(phrase)
                if res:
                    if isinstance(res, list):
                        matches += res
                    else:
                        matches.append(res)
        return matches


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
                self.items.append((item, po.x1, po.y1))

    def put_objects(self):
        for block, x, y in self.items:
            self.layout_block(block, x, y)

    def layout_block(self, block, x, y):
        block.reset()
        _Canvas.layout_block(self, block, x, y)


class Header(Canvas):

    def __init__(self, font_loader, header, page_style, logger, opts, ruby_tags, link_activated):
        Canvas.__init__(self, font_loader, header, logger, opts, ruby_tags, link_activated,
                        page_style.textwidth,  page_style.headheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.DashLine))


class Footer(Canvas):

    def __init__(self, font_loader, footer, page_style, logger, opts, ruby_tags, link_activated):
        Canvas.__init__(self, font_loader, footer, logger, opts, ruby_tags, link_activated,
                        page_style.textwidth, page_style.footheight)
        if opts.visual_debug:
            self.setPen(QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.DashLine))


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
            self.setPen(QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.SolidLine))
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
            self.setPen(QPen(Qt.GlobalColor.cyan, 1, Qt.PenStyle.DashLine))

    def id(self):
        for child in self.children():
            if hasattr(child, 'block_id'):
                return child.block_id

    def add_block(self, block):
        self.layout_block(block, 0, self.current_y)


class Chapter:

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

    def search(self, phrase):
        pages = []
        for i in range(len(self.pages)):
            matches = self.pages[i].search(phrase)
            if matches:
                pages.append([i, matches])
        return pages


class History(collections.deque):

    def __init__(self):
        collections.deque.__init__(self)
        self.pos = 0

    def back(self):
        if self.pos - 1 < 0:
            return None
        self.pos -= 1
        return self[self.pos]

    def forward(self):
        if self.pos + 1 >= len(self):
            return None
        self.pos += 1
        return self[self.pos]

    def add(self, item):
        while len(self) > self.pos+1:
            self.pop()
        self.append(item)
        self.pos += 1


class Document(QGraphicsScene):

    num_of_pages = property(fget=lambda self: sum(self.chapter_layout or ()))
    chapter_rendered = pyqtSignal(object)
    page_changed = pyqtSignal(object)

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
        self.last_search = iter([])
        if not opts.white_background:
            self.setBackgroundBrush(QBrush(QColor(0xee, 0xee, 0xee)))

    def page_of(self, oid):
        for chapter in self.chapters:
            if oid in chapter.object_to_page_map:
                return chapter.object_to_page_map[oid]

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
            if oid is not None:
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

    def load_fonts(self, lrf, load_substitutions=True):
        font_map = {}

        for font in lrf.font_map:
            fdata = QByteArray(lrf.font_map[font].data)
            id = QFontDatabase.addApplicationFontFromData(fdata)
            if id != -1:
                font_map[font] = [str(i) for i in QFontDatabase.applicationFontFamilies(id)][0]

        if load_substitutions:
            base = P('fonts/liberation/*.ttf')
            for f in glob.glob(base):
                QFontDatabase.addApplicationFont(f)

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
            object_to_page_map[object.id] = len(pages) + 1
            while block.has_content:
                current_page.add_block(block)
                if current_page.is_full:
                    pages.append(current_page)
                    current_page = Page(self.font_loader, self.logger, self.opts, width, height)
        if current_page:
            pages.append(current_page)
        self.chapters.append(Chapter(oddscreen, evenscreen, pages, object_to_page_map))
        self.chapter_map[chapter.id] = len(self.chapters)-1

    def render(self, lrf, load_substitutions=True):
        self.dpi = lrf.device_info.dpi/10.
        self.ruby_tags = dict(**lrf.ruby_tags)
        self.load_fonts(lrf, load_substitutions)
        self.objects = lrf.objects

        num_chaps = 0
        for pt in lrf.page_trees:
            for chapter in pt:
                num_chaps += 1
        self.chapter_rendered.emit(num_chaps)

        for pt in lrf.page_trees:
            for chapter in pt:
                self.render_chapter(chapter, lrf)
                self.chapter_rendered.emit(-1)
        self.chapter_layout = [i.num_of_pages for i in self.chapters]
        self.objects = None

    def chapter_page(self, num):
        for chapter in self.chapters:
            if num <= chapter.num_of_pages:
                break
            num -= chapter.num_of_pages
        return chapter, chapter.page(num)

    def show_page(self, num):
        num = int(num)
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
        self.page_changed.emit(self.current_page)

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

    def search(self, phrase):
        if not phrase:
            return
        matches = []
        for i in range(len(self.chapters)):
            cmatches = self.chapters[i].search(phrase)
            for match in cmatches:
                match[0] += sum(self.chapter_layout[:i])+1
            matches += cmatches
        self.last_search = itertools.cycle(matches)
        self.next_match()

    def next_match(self):
        page_num = next(self.last_search)[0]
        if self.current_page == page_num:
            self.update()
        else:
            self.add_to_history()
            self.show_page(page_num)
