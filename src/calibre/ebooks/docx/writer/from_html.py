#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from collections import Counter

from calibre.ebooks.docx.writer.container import create_skeleton, page_size
from calibre.ebooks.docx.writer.styles import StylesManager, FloatSpec
from calibre.ebooks.docx.writer.links import LinksManager
from calibre.ebooks.docx.writer.images import ImagesManager
from calibre.ebooks.docx.writer.fonts import FontsManager
from calibre.ebooks.docx.writer.tables import Table
from calibre.ebooks.docx.writer.lists import ListsManager
from calibre.ebooks.oeb.stylizer import Stylizer as Sz, Style as St
from calibre.ebooks.oeb.base import XPath, barename
from calibre.utils.localization import lang_as_iso639_1


def lang_for_tag(tag):
    for attr in ('lang', '{http://www.w3.org/XML/1998/namespace}lang'):
        val = lang_as_iso639_1(tag.get(attr))
        if val:
            return val


class Style(St):

    def __init__(self, *args, **kwargs):
        St.__init__(self, *args, **kwargs)
        self._letterSpacing = None

    @property
    def letterSpacing(self):
        if self._letterSpacing is not None:
            val = self._get('letter-spacing')
            if val == 'normal':
                self._letterSpacing = val
            else:
                self._letterSpacing = self._unit_convert(val)
        return self._letterSpacing


class Stylizer(Sz):

    def style(self, element):
        try:
            return self._styles[element]
        except KeyError:
            return Style(element, self)


class TextRun(object):

    ws_pat = None

    def __init__(self, namespace, style, first_html_parent, lang=None):
        self.first_html_parent = first_html_parent
        if self.ws_pat is None:
            TextRun.ws_pat = self.ws_pat = re.compile(r'\s+')
        self.style = style
        self.texts = []
        self.link = None
        self.lang = lang
        self.parent_style = None
        self.makeelement = namespace.makeelement
        self.descendant_style = None

    def add_text(self, text, preserve_whitespace, bookmark=None, link=None):
        if not preserve_whitespace:
            text = self.ws_pat.sub(' ', text)
            if text.strip() != text:
                # If preserve_whitespace is False, Word ignores leading and
                # trailing whitespace
                preserve_whitespace = True
        self.texts.append((text, preserve_whitespace, bookmark))
        self.link = link

    def add_break(self, clear='none', bookmark=None):
        self.texts.append((None, clear, bookmark))

    def add_image(self, drawing, bookmark=None):
        self.texts.append((drawing, None, bookmark))

    def serialize(self, p, links_manager):
        makeelement = self.makeelement
        parent = p if self.link is None else links_manager.serialize_hyperlink(p, self.link)
        r = makeelement(parent, 'w:r')
        rpr = makeelement(r, 'w:rPr', append=False)
        if getattr(self.descendant_style, 'id', None) is not None:
            makeelement(rpr, 'w:rStyle', w_val=self.descendant_style.id)
        if self.lang:
            makeelement(rpr, 'w:lang', w_bidi=self.lang, w_val=self.lang, w_eastAsia=self.lang)
        if len(rpr) > 0:
            r.append(rpr)

        for text, preserve_whitespace, bookmark in self.texts:
            if bookmark is not None:
                bid = links_manager.bookmark_id
                makeelement(r, 'w:bookmarkStart', w_id=str(bid), w_name=bookmark)
            if text is None:
                makeelement(r, 'w:br', w_clear=preserve_whitespace)
            elif hasattr(text, 'xpath'):
                r.append(text)
            else:
                t = makeelement(r, 'w:t')
                t.text = text or ''
                if preserve_whitespace:
                    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            if bookmark is not None:
                makeelement(r, 'w:bookmarkEnd', w_id=str(bid))

    def __repr__(self):
        return repr(self.texts)

    def is_empty(self):
        if not self.texts:
            return True
        if len(self.texts) == 1 and self.texts[0][:2] == ('', False):
            return True
        return False

    @property
    def style_weight(self):
        ans = 0
        for text, preserve_whitespace, bookmark in self.texts:
            if isinstance(text, type('')):
                ans += len(text)
        return ans


class Block(object):

    def __init__(self, namespace, styles_manager, links_manager, html_block, style, is_table_cell=False, float_spec=None, is_list_item=False):
        self.namespace = namespace
        self.bookmarks = set()
        self.list_tag = (html_block, style) if is_list_item else None
        self.is_first_block = False
        self.numbering_id = None
        self.parent_items = None
        self.html_block = html_block
        self.html_tag = barename(html_block.tag)
        self.float_spec = float_spec
        if float_spec is not None:
            float_spec.blocks.append(self)
        self.html_style = style
        self.style = styles_manager.create_block_style(style, html_block, is_table_cell=is_table_cell)
        self.styles_manager, self.links_manager = styles_manager, links_manager
        self.keep_next = False
        self.runs = []
        self.skipped = False
        self.linked_style = None
        self.page_break_before = style['page-break-before'] == 'always'
        self.keep_lines = style['page-break-inside'] == 'avoid'
        self.page_break_after = False
        self.block_lang = None

    def resolve_skipped(self, next_block):
        if not self.is_empty():
            return
        if len(self.html_block) > 0 and self.html_block[0] is next_block.html_block:
            self.skipped = True
            if self.list_tag is not None:
                next_block.list_tag = self.list_tag

    def add_text(self, text, style, ignore_leading_whitespace=False, html_parent=None, is_parent_style=False, bookmark=None, link=None, lang=None):
        ts = self.styles_manager.create_text_style(style, is_parent_style=is_parent_style)
        ws = style['white-space']
        if self.runs and ts == self.runs[-1].style and link == self.runs[-1].link and lang == self.runs[-1].lang:
            run = self.runs[-1]
        else:
            run = TextRun(self.namespace, ts, self.html_block if html_parent is None else html_parent, lang=lang)
            self.runs.append(run)
        preserve_whitespace = ws in {'pre', 'pre-wrap'}
        if ignore_leading_whitespace and not preserve_whitespace:
            text = text.lstrip()
        if ws == 'pre-line':
            for text in text.splitlines():
                run.add_text(text, False, bookmark=bookmark, link=link)
                bookmark = None
                run.add_break()
        else:
            run.add_text(text, preserve_whitespace, bookmark=bookmark, link=link)

    def add_break(self, clear='none', bookmark=None):
        if self.runs:
            run = self.runs[-1]
        else:
            run = TextRun(self.namespace, self.styles_manager.create_text_style(self.html_style), self.html_block)
            self.runs.append(run)
        run.add_break(clear=clear, bookmark=bookmark)

    def add_image(self, drawing, bookmark=None):
        if self.runs:
            run = self.runs[-1]
        else:
            run = TextRun(self.namespace, self.styles_manager.create_text_style(self.html_style), self.html_block)
            self.runs.append(run)
        run.add_image(drawing, bookmark=bookmark)

    def serialize(self, body):
        makeelement = self.namespace.makeelement
        p = makeelement(body, 'w:p')
        end_bookmarks = []
        for bmark in self.bookmarks:
            end_bookmarks.append(str(self.links_manager.bookmark_id))
            makeelement(p, 'w:bookmarkStart', w_id=end_bookmarks[-1], w_name=bmark)
        if self.block_lang:
            rpr = makeelement(p, 'w:rPr')
            makeelement(rpr, 'w:lang', w_val=self.block_lang, w_bidi=self.block_lang, w_eastAsia=self.block_lang)

        ppr = makeelement(p, 'w:pPr')
        if self.keep_next:
            makeelement(ppr, 'w:keepNext')
        if self.float_spec is not None:
            self.float_spec.serialize(self, ppr)
        if self.numbering_id is not None:
            numpr = makeelement(ppr, 'w:numPr')
            makeelement(numpr, 'w:ilvl', w_val=str(self.numbering_id[1]))
            makeelement(numpr, 'w:numId', w_val=str(self.numbering_id[0]))
        if self.linked_style is not None:
            makeelement(ppr, 'w:pStyle', w_val=self.linked_style.id)
        elif self.style.id:
            makeelement(ppr, 'w:pStyle', w_val=self.style.id)
        if self.is_first_block:
            makeelement(ppr, 'w:pageBreakBefore', w_val='off')
        elif self.page_break_before:
            makeelement(ppr, 'w:pageBreakBefore', w_val='on')
        if self.keep_lines:
            makeelement(ppr, 'w:keepLines', w_val='on')
        for run in self.runs:
            run.serialize(p, self.links_manager)
        for bmark in end_bookmarks:
            makeelement(p, 'w:bookmarkEnd', w_id=bmark)

    def __repr__(self):
        return 'Block(%r)' % self.runs
    __str__ = __repr__

    def is_empty(self):
        for run in self.runs:
            if not run.is_empty():
                return False
        return True


class Blocks(object):

    def __init__(self, namespace, styles_manager, links_manager):
        self.namespace = namespace
        self.styles_manager = styles_manager
        self.links_manager = links_manager
        self.all_blocks = []
        self.pos = 0
        self.current_block = None
        self.items = []
        self.tables = []
        self.current_table = None
        self.open_html_blocks = set()
        self.html_tag_start_blocks = {}

    def current_or_new_block(self, html_tag, tag_style):
        return self.current_block or self.start_new_block(html_tag, tag_style)

    def end_current_block(self):
        if self.current_block is not None:
            self.all_blocks.append(self.current_block)
            if self.current_table is not None and self.current_table.current_row is not None:
                self.current_table.add_block(self.current_block)
            else:
                self.block_map[self.current_block] = len(self.items)
                self.items.append(self.current_block)
                self.current_block.parent_items = self.items
        self.current_block = None

    def start_new_block(self, html_block, style, is_table_cell=False, float_spec=None, is_list_item=False):
        self.end_current_block()
        self.current_block = Block(
            self.namespace, self.styles_manager, self.links_manager, html_block, style,
            is_table_cell=is_table_cell, float_spec=float_spec, is_list_item=is_list_item)
        self.html_tag_start_blocks[html_block] = self.current_block
        self.open_html_blocks.add(html_block)
        return self.current_block

    def start_new_table(self, html_tag, tag_style=None):
        self.current_table = Table(self.namespace, html_tag, tag_style)
        self.tables.append(self.current_table)

    def start_new_row(self, html_tag, tag_style):
        if self.current_table is None:
            self.start_new_table(html_tag)
        self.current_table.start_new_row(html_tag, tag_style)

    def start_new_cell(self, html_tag, tag_style):
        if self.current_table is None:
            self.start_new_table(html_tag)
        self.current_table.start_new_cell(html_tag, tag_style)

    def finish_tag(self, html_tag):
        if self.current_block is not None and html_tag in self.open_html_blocks:
            start_block = self.html_tag_start_blocks.get(html_tag)
            if start_block is not None and start_block.html_style['page-break-after'] == 'always':
                self.current_block.page_break_after = True
            self.end_current_block()
            self.open_html_blocks.discard(html_tag)

        if self.current_table is not None:
            table_finished = self.current_table.finish_tag(html_tag)
            if table_finished:
                table = self.tables[-1]
                del self.tables[-1]
                if self.tables:
                    self.current_table = self.tables[-1]
                    self.current_table.add_table(table)
                else:
                    self.current_table = None
                    self.block_map[table] = len(self.items)
                    self.items.append(table)

    def serialize(self, body):
        for item in self.items:
            item.serialize(body)

    def delete_block_at(self, pos=None):
        pos = self.pos if pos is None else pos
        block = self.all_blocks[pos]
        del self.all_blocks[pos]
        bpos = self.block_map.pop(block, None)
        if bpos is not None:
            del self.items[bpos]
        else:
            items = self.items if block.parent_items is None else block.parent_items
            items.remove(block)
        block.parent_items = None
        if block.float_spec is not None:
            block.float_spec.blocks.remove(block)
        try:
            next_block = self.all_blocks[pos]
            next_block.bookmarks.update(block.bookmarks)
            for attr in 'page_break_after page_break_before'.split():
                setattr(next_block, attr, getattr(block, attr))
        except (IndexError, KeyError):
            pass

    def __enter__(self):
        self.pos = len(self.all_blocks)
        self.block_map = {}

    def __exit__(self, etype, value, traceback):
        if value is not None:
            return  # Since there was an exception, the data structures are not in a consistent state
        if self.current_block is not None:
            self.all_blocks.append(self.current_block)
        self.current_block = None
        if len(self.all_blocks) > self.pos and self.all_blocks[self.pos].is_empty():
            # Delete the empty block corresponding to the <body> tag when the
            # body tag has no inline content before its first sub-block
            self.delete_block_at(self.pos)
        if self.pos > 0 and self.pos < len(self.all_blocks):
            # Insert a page break corresponding to the start of the html file
            self.all_blocks[self.pos].page_break_before = True
        self.block_map = {}

    def apply_page_break_after(self):
        for i, block in enumerate(self.all_blocks):
            if block.page_break_after and i < len(self.all_blocks) - 1:
                next_block = self.all_blocks[i + 1]
                if next_block.parent_items is block.parent_items and block.parent_items is self.items:
                    next_block.page_break_before = True

    def resolve_language(self):
        default_lang = self.styles_manager.document_lang
        for block in self.all_blocks:
            count = Counter()
            for run in block.runs:
                count[run.lang] += 1
            if count:
                block.block_lang = bl = count.most_common(1)[0][0]
                for run in block.runs:
                    if run.lang == bl:
                        run.lang = None
                if bl == default_lang:
                    block.block_lang = None

    def __repr__(self):
        return 'Block(%r)' % self.runs


class Convert(object):

    # Word does not apply default styling to hyperlinks, so we ensure they get
    # default styling (the conversion pipeline does not apply any styling to
    # them).
    base_css = '''
    a[href] { text-decoration: underline; color: blue }
    '''

    def __init__(self, oeb, docx, mi, add_cover, add_toc):
        self.oeb, self.docx, self.add_cover, self.add_toc = oeb, docx, add_cover, add_toc
        self.log, self.opts = docx.log, docx.opts
        self.mi = mi
        self.cover_img = None

    def __call__(self):
        from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
        self.svg_rasterizer = SVGRasterizer(base_css=self.base_css)
        self.svg_rasterizer(self.oeb, self.opts)

        self.styles_manager = StylesManager(self.docx.namespace, self.log, self.mi.language)
        self.links_manager = LinksManager(self.docx.namespace, self.docx.document_relationships, self.log)
        self.images_manager = ImagesManager(self.oeb, self.docx.document_relationships)
        self.lists_manager = ListsManager(self.docx)
        self.fonts_manager = FontsManager(self.docx.namespace, self.oeb, self.opts)
        self.blocks = Blocks(self.docx.namespace, self.styles_manager, self.links_manager)
        self.current_link = self.current_lang = None

        for item in self.oeb.spine:
            self.log.debug('Processing', item.href)
            self.process_item(item)
        if self.add_toc:
            self.links_manager.process_toc_links(self.oeb)

        if self.add_cover and self.oeb.metadata.cover and unicode(self.oeb.metadata.cover[0]) in self.oeb.manifest.ids:
            cover_id = unicode(self.oeb.metadata.cover[0])
            item = self.oeb.manifest.ids[cover_id]
            self.cover_img = self.images_manager.read_image(item.href)

        all_blocks = self.blocks.all_blocks
        remove_blocks = []
        for i, block in enumerate(all_blocks):
            try:
                nb = all_blocks[i+1]
            except IndexError:
                break
            block.resolve_skipped(nb)
            if block.skipped:
                remove_blocks.append((i, block))
        for pos, block in reversed(remove_blocks):
            self.blocks.delete_block_at(pos)
        self.blocks.all_blocks[0].is_first_block = True
        self.blocks.apply_page_break_after()
        self.blocks.resolve_language()

        if self.cover_img is not None:
            self.cover_img = self.images_manager.create_cover_markup(self.cover_img, *page_size(self.opts))
        self.lists_manager.finalize(all_blocks)
        self.styles_manager.finalize(all_blocks)
        self.write()

    def process_item(self, item):
        self.current_item = item
        stylizer = self.svg_rasterizer.stylizer_cache.get(item)
        if stylizer is None:
            stylizer = Stylizer(item.data, item.href, self.oeb, self.opts, self.opts.output_profile, base_css=self.base_css)
        self.abshref = self.images_manager.abshref = item.abshref

        self.current_lang = lang_for_tag(item.data) or self.styles_manager.document_lang
        for i, body in enumerate(XPath('//h:body')(item.data)):
            with self.blocks:
                self.links_manager.bookmark_for_anchor(self.links_manager.top_anchor, self.current_item, body)
                self.process_tag(body, stylizer, is_first_tag=i == 0)

    def process_tag(self, html_tag, stylizer, is_first_tag=False, float_spec=None):
        tagname = barename(html_tag.tag)
        if tagname in {'script', 'style', 'title', 'meta'}:
            return
        tag_style = stylizer.style(html_tag)
        if tag_style.is_hidden:
            return

        previous_link = self.current_link
        if tagname == 'a' and html_tag.get('href'):
            self.current_link = (self.current_item, html_tag.get('href'), html_tag.get('title'))
        previous_lang = self.current_lang
        tag_lang = lang_for_tag(html_tag)
        if tag_lang:
            self.current_lang = tag_lang

        display = tag_style._get('display')
        is_float = tag_style['float'] in {'left', 'right'} and not is_first_tag
        if float_spec is None and is_float:
            float_spec = FloatSpec(self.docx.namespace, html_tag, tag_style)

        if display in {'inline', 'inline-block'} or tagname == 'br':  # <br> has display:block but we dont want to start a new paragraph
            if is_float and float_spec.is_dropcaps:
                self.add_block_tag(tagname, html_tag, tag_style, stylizer, float_spec=float_spec)
                float_spec = None
            else:
                self.add_inline_tag(tagname, html_tag, tag_style, stylizer)
        elif display == 'list-item':
            self.add_block_tag(tagname, html_tag, tag_style, stylizer, is_list_item=True)
        elif display.startswith('table') or display == 'inline-table':
            if display == 'table-cell':
                self.blocks.start_new_cell(html_tag, tag_style)
                self.add_block_tag(tagname, html_tag, tag_style, stylizer, is_table_cell=True)
            elif display == 'table-row':
                self.blocks.start_new_row(html_tag, tag_style)
            elif display in {'table', 'inline-table'}:
                self.blocks.end_current_block()
                self.blocks.start_new_table(html_tag, tag_style)
        else:
            if tagname == 'img' and is_float:
                # Image is floating so dont start a new paragraph for it
                self.add_inline_tag(tagname, html_tag, tag_style, stylizer)
            else:
                if tagname == 'hr':
                    for edge in 'right bottom left'.split():
                        tag_style.set('border-%s-style' % edge, 'none')
                self.add_block_tag(tagname, html_tag, tag_style, stylizer, float_spec=float_spec)

        for child in html_tag.iterchildren('*'):
            self.process_tag(child, stylizer, float_spec=float_spec)

        is_block = html_tag in self.blocks.open_html_blocks
        self.blocks.finish_tag(html_tag)
        if is_block and tag_style['page-break-after'] == 'avoid':
            self.blocks.all_blocks[-1].keep_next = True

        self.current_link = previous_link
        self.current_lang = previous_lang

        if display == 'table-row':
            return  # We ignore the tail for these tags

        ignore_whitespace_tail = is_block or display.startswith('table')
        if not is_first_tag and html_tag.tail and (not ignore_whitespace_tail or not html_tag.tail.isspace()):
            # Ignore trailing space after a block tag, as otherwise it will
            # become a new empty paragraph
            block = self.create_block_from_parent(html_tag, stylizer)
            block.add_text(html_tag.tail, stylizer.style(html_tag.getparent()), is_parent_style=True, link=self.current_link, lang=self.current_lang)

    def create_block_from_parent(self, html_tag, stylizer):
        parent = html_tag.getparent()
        block = self.blocks.current_or_new_block(parent, stylizer.style(parent))
        # Do not inherit page-break-before from parent
        block.page_break_before = False
        return block

    def add_block_tag(self, tagname, html_tag, tag_style, stylizer, is_table_cell=False, float_spec=None, is_list_item=False):
        block = self.blocks.start_new_block(
            html_tag, tag_style, is_table_cell=is_table_cell, float_spec=float_spec, is_list_item=is_list_item)
        anchor = html_tag.get('id') or html_tag.get('name')
        if anchor:
            block.bookmarks.add(self.bookmark_for_anchor(anchor, html_tag))
        if tagname == 'img':
            self.images_manager.add_image(html_tag, block, stylizer, as_block=True)
        else:
            if html_tag.text:
                block.add_text(html_tag.text, tag_style, ignore_leading_whitespace=True, is_parent_style=True, link=self.current_link, lang=self.current_lang)

    def add_inline_tag(self, tagname, html_tag, tag_style, stylizer):
        anchor = html_tag.get('id') or html_tag.get('name') or None
        bmark = None
        if anchor:
            bmark = self.bookmark_for_anchor(anchor, html_tag)
        if tagname == 'br':
            if html_tag.tail or html_tag is not tuple(html_tag.getparent().iterchildren('*'))[-1]:
                block = self.create_block_from_parent(html_tag, stylizer)
                block.add_break(clear={'both':'all', 'left':'left', 'right':'right'}.get(tag_style['clear'], 'none'), bookmark=bmark)
        elif tagname == 'img':
            block = self.create_block_from_parent(html_tag, stylizer)
            self.images_manager.add_image(html_tag, block, stylizer, bookmark=bmark)
        else:
            if html_tag.text:
                block = self.create_block_from_parent(html_tag, stylizer)
                block.add_text(html_tag.text, tag_style, is_parent_style=False, bookmark=bmark, link=self.current_link, lang=self.current_lang)
            elif bmark:
                block = self.create_block_from_parent(html_tag, stylizer)
                block.add_text('', tag_style, is_parent_style=False, bookmark=bmark, link=self.current_link, lang=self.current_lang)

    def bookmark_for_anchor(self, anchor, html_tag):
        return self.links_manager.bookmark_for_anchor(anchor, self.current_item, html_tag)

    def write(self):
        self.docx.document, self.docx.styles, body = create_skeleton(self.opts)
        self.blocks.serialize(body)
        body.append(body[0])  # Move <sectPr> to the end
        if self.links_manager.toc:
            self.links_manager.serialize_toc(body, self.styles_manager.primary_heading_style)
        if self.cover_img is not None:
            self.images_manager.write_cover_block(body, self.cover_img)
        self.styles_manager.serialize(self.docx.styles)
        self.images_manager.serialize(self.docx.images)
        self.fonts_manager.serialize(self.styles_manager.text_styles, self.docx.font_table, self.docx.embedded_fonts, self.docx.fonts)
        self.lists_manager.serialize(self.docx.numbering)
