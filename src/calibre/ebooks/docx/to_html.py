#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, re
from collections import OrderedDict, defaultdict

from lxml import html
from lxml.html.builder import (
    HTML, HEAD, TITLE, BODY, LINK, META, P, SPAN, BR, DIV, SUP, A, DT, DL, DD, H1)

from calibre.ebooks.docx.container import DOCX, fromstring
from calibre.ebooks.docx.names import (
    XPath, is_tag, XML, STYLES, NUMBERING, FONTS, get, generate_anchor,
    descendants, ancestor, FOOTNOTES, ENDNOTES)
from calibre.ebooks.docx.styles import Styles, inherit, PageProperties
from calibre.ebooks.docx.numbering import Numbering
from calibre.ebooks.docx.fonts import Fonts
from calibre.ebooks.docx.images import Images
from calibre.ebooks.docx.footnotes import Footnotes
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1

class Text:

    def __init__(self, elem, attr, buf):
        self.elem, self.attr, self.buf = elem, attr, buf

    def add_elem(self, elem):
        setattr(self.elem, self.attr, ''.join(self.buf))
        self.elem, self.attr, self.buf = elem, 'tail', []

class Convert(object):

    def __init__(self, path_or_stream, dest_dir=None, log=None, notes_text=None):
        self.docx = DOCX(path_or_stream, log=log)
        self.log = self.docx.log
        self.notes_text = notes_text or _('Notes')
        self.dest_dir = dest_dir or os.getcwdu()
        self.mi = self.docx.metadata
        self.body = BODY()
        self.styles = Styles()
        self.images = Images()
        self.object_map = OrderedDict()
        self.html = HTML(
            HEAD(
                META(charset='utf-8'),
                TITLE(self.mi.title or _('Unknown')),
                LINK(rel='stylesheet', type='text/css', href='docx.css'),
            ),
            self.body
        )
        self.html.text='\n\t'
        self.html[0].text='\n\t\t'
        self.html[0].tail='\n'
        for child in self.html[0]:
            child.tail = '\n\t\t'
        self.html[0][-1].tail = '\n\t'
        self.html[1].text = self.html[1].tail = '\n'
        lang = canonicalize_lang(self.mi.language)
        if lang and lang != 'und':
            lang = lang_as_iso639_1(lang)
            if lang:
                self.html.set('lang', lang)

    def __call__(self):
        doc = self.docx.document
        relationships_by_id, relationships_by_type = self.docx.document_relationships
        self.read_styles(relationships_by_type)
        self.images(relationships_by_id)
        self.layers = OrderedDict()
        self.framed = [[]]
        self.framed_map = {}
        self.anchor_map = {}
        self.link_map = defaultdict(list)

        self.read_page_properties(doc)
        for wp, page_properties in self.page_map.iteritems():
            self.current_page = page_properties
            p = self.convert_p(wp)
            self.body.append(p)

        notes_header = None
        if self.footnotes.has_notes:
            dl = DL()
            dl.set('class', 'notes')
            self.body.append(H1(self.notes_text))
            notes_header = self.body[-1]
            notes_header.set('class', 'notes-header')
            self.body.append(dl)
            for anchor, text, note in self.footnotes:
                dl.append(DT('[', A('←' + text, href='#back_%s' % anchor, title=text), id=anchor))
                dl[-1][0].tail = ']'
                dl.append(DD())
                for wp in note:
                    p = self.convert_p(wp)
                    dl[-1].append(p)

        self.resolve_links(relationships_by_id)
        # TODO: tables <w:tbl> child of <w:body> (nested tables?)

        self.styles.cascade(self.layers)

        numbered = []
        for html_obj, obj in self.object_map.iteritems():
            raw = obj.get('calibre_num_id', None)
            if raw is not None:
                lvl, num_id = raw.partition(':')[0::2]
                try:
                    lvl = int(lvl)
                except (TypeError, ValueError):
                    lvl = 0
                numbered.append((html_obj, num_id, lvl))
        self.numbering.apply_markup(numbered, self.body, self.styles, self.object_map)
        self.apply_frames()

        if len(self.body) > 0:
            self.body.text = '\n\t'
            for child in self.body:
                child.tail = '\n\t'
            self.body[-1].tail = '\n'

        self.styles.generate_classes()
        for html_obj, obj in self.object_map.iteritems():
            style = self.styles.resolve(obj)
            if style is not None:
                css = style.css
                if css:
                    cls = self.styles.class_name(css)
                    if cls:
                        html_obj.set('class', cls)
        for html_obj, css in self.framed_map.iteritems():
            cls = self.styles.class_name(css)
            if cls:
                html_obj.set('class', cls)

        if notes_header is not None:
            for h in self.body.iterchildren('h1', 'h2', 'h3'):
                notes_header.tag = h.tag
                cls = h.get('class', None)
                if cls and cls != 'notes-header':
                    notes_header.set('class', '%s notes-header' % cls)
                break

        return self.write()

    def read_page_properties(self, doc):
        current = []
        self.page_map = OrderedDict()

        for p in descendants(doc, 'w:p'):
            sect = tuple(descendants(p, 'w:sectPr'))
            if sect:
                pr = PageProperties(sect)
                for x in current + [p]:
                    self.page_map[x] = pr
                current = []
            else:
                current.append(p)
        if current:
            last = XPath('./w:body/w:sectPr')(doc)
            pr = PageProperties(last)
            for x in current:
                self.page_map[x] = pr

    def read_styles(self, relationships_by_type):

        def get_name(rtype, defname):
            name = relationships_by_type.get(rtype, None)
            if name is None:
                cname = self.docx.document_name.split('/')
                cname[-1] = defname
                if self.docx.exists('/'.join(cname)):
                    name = name
            return name

        nname = get_name(NUMBERING, 'numbering.xml')
        sname = get_name(STYLES, 'styles.xml')
        fname = get_name(FONTS, 'fontTable.xml')
        foname = get_name(FOOTNOTES, 'footnotes.xml')
        enname = get_name(ENDNOTES, 'endnotes.xml')
        numbering = self.numbering = Numbering()
        footnotes = self.footnotes = Footnotes()
        fonts = self.fonts = Fonts()

        foraw = enraw = None
        if foname is not None:
            try:
                foraw = self.docx.read(foname)
            except KeyError:
                self.log.warn('Footnotes %s do not exist' % foname)
        if enname is not None:
            try:
                enraw = self.docx.read(enname)
            except KeyError:
                self.log.warn('Endnotes %s do not exist' % enname)
        footnotes(fromstring(foraw) if foraw else None, fromstring(enraw) if enraw else None)

        if fname is not None:
            embed_relationships = self.docx.get_relationships(fname)[0]
            try:
                raw = self.docx.read(fname)
            except KeyError:
                self.log.warn('Fonts table %s does not exist' % fname)
            else:
                fonts(fromstring(raw), embed_relationships, self.docx, self.dest_dir)

        if sname is not None:
            try:
                raw = self.docx.read(sname)
            except KeyError:
                self.log.warn('Styles %s do not exist' % sname)
            else:
                self.styles(fromstring(raw), fonts)

        if nname is not None:
            try:
                raw = self.docx.read(nname)
            except KeyError:
                self.log.warn('Numbering styles %s do not exist' % nname)
            else:
                numbering(fromstring(raw), self.styles)

        self.styles.resolve_numbering(numbering)

    def write(self):
        raw = html.tostring(self.html, encoding='utf-8', doctype='<!DOCTYPE html>')
        with open(os.path.join(self.dest_dir, 'index.html'), 'wb') as f:
            f.write(raw)
        css = self.styles.generate_css(self.dest_dir, self.docx)
        if css:
            with open(os.path.join(self.dest_dir, 'docx.css'), 'wb') as f:
                f.write(css.encode('utf-8'))

        opf = OPFCreator(self.dest_dir, self.mi)
        opf.create_manifest_from_files_in([self.dest_dir])
        opf.create_spine(['index.html'])
        with open(os.path.join(self.dest_dir, 'metadata.opf'), 'wb') as of, open(os.path.join(self.dest_dir, 'toc.ncx'), 'wb') as ncx:
            opf.render(of, ncx, 'toc.ncx')
        return os.path.join(self.dest_dir, 'metadata.opf')

    def convert_p(self, p):
        dest = P()
        self.object_map[dest] = p
        style = self.styles.resolve_paragraph(p)
        self.layers[p] = []
        self.add_frame(dest, style.frame)

        current_anchor = None
        current_hyperlink = None

        for x in descendants(p, 'w:r', 'w:bookmarkStart', 'w:hyperlink'):
            if x.tag.endswith('}r'):
                span = self.convert_run(x)
                if current_anchor is not None:
                    (dest if len(dest) == 0 else span).set('id', current_anchor)
                    current_anchor = None
                if current_hyperlink is not None:
                    hl = ancestor(x, 'w:hyperlink')
                    if hl is not None:
                        self.link_map[hl].append(span)
                    else:
                        current_hyperlink = None
                dest.append(span)
                self.layers[p].append(x)
            elif x.tag.endswith('}bookmarkStart'):
                anchor = get(x, 'w:name')
                if anchor and anchor not in self.anchor_map:
                    self.anchor_map[anchor] = current_anchor = generate_anchor(anchor, frozenset(self.anchor_map.itervalues()))
            elif x.tag.endswith('}hyperlink'):
                current_hyperlink = x

        m = re.match(r'heading\s+(\d+)$', style.style_name or '', re.IGNORECASE)
        if m is not None:
            n = min(1, max(6, int(m.group(1))))
            dest.tag = 'h%d' % n

        if style.direction == 'rtl':
            dest.set('dir', 'rtl')

        border_runs = []
        common_borders = []
        for span in dest:
            run = self.object_map[span]
            style = self.styles.resolve_run(run)
            if not border_runs or border_runs[-1][1].same_border(style):
                border_runs.append((span, style))
            elif border_runs:
                if len(border_runs) > 1:
                    common_borders.append(border_runs)
                border_runs = []

        for border_run in common_borders:
            spans = []
            bs = {}
            for span, style in border_run:
                style.get_border_css(bs)
                style.clear_border_css()
                spans.append(span)
            if bs:
                cls = self.styles.register(bs, 'text_border')
                wrapper = self.wrap_elems(spans, SPAN())
                wrapper.set('class', cls)

        return dest

    def wrap_elems(self, elems, wrapper):
        p = elems[0].getparent()
        idx = p.index(elems[0])
        p.insert(idx, wrapper)
        wrapper.tail = elems[-1].tail
        elems[-1].tail = None
        for elem in elems:
            p.remove(elem)
            wrapper.append(elem)
        return wrapper

    def resolve_links(self, relationships_by_id):
        for hyperlink, spans in self.link_map.iteritems():
            span = spans[0]
            if len(spans) > 1:
                span = self.wrap_elems(spans, SPAN())
            span.tag = 'a'
            tgt = get(hyperlink, 'w:tgtFrame')
            if tgt:
                span.set('target', tgt)
            tt = get(hyperlink, 'w:tooltip')
            if tt:
                span.set('title', tt)
            rid = get(hyperlink, 'r:id')
            if rid and rid in relationships_by_id:
                span.set('href', relationships_by_id[rid])
                continue
            anchor = get(hyperlink, 'w:anchor')
            if anchor and anchor in self.anchor_map:
                span.set('href', '#' + self.anchor_map[anchor])
                continue
            self.log.warn('Hyperlink with unknown target (%s, %s), ignoring' %
                          (rid, anchor))
            span.set('href', '#')

    def convert_run(self, run):
        ans = SPAN()
        self.object_map[ans] = run
        text = Text(ans, 'text', [])

        for child in run:
            if is_tag(child, 'w:t'):
                if not child.text:
                    continue
                space = child.get(XML('space'), None)
                if space == 'preserve':
                    text.add_elem(SPAN(child.text, style="whitespace:pre-wrap"))
                    ans.append(text.elem)
                else:
                    text.buf.append(child.text)
            elif is_tag(child, 'w:cr'):
                text.add_elem(BR())
                ans.append(text.elem)
            elif is_tag(child, 'w:br'):
                typ = child.get('type', None)
                if typ in {'column', 'page'}:
                    br = BR(style='page-break-after:always')
                else:
                    clear = child.get('clear', None)
                    if clear in {'all', 'left', 'right'}:
                        br = BR(style='clear:%s'%('both' if clear == 'all' else clear))
                    else:
                        br = BR()
                text.add_elem(br)
                ans.append(text.elem)
            elif is_tag(child, 'w:drawing') or is_tag(child, 'w:pict'):
                for img in self.images.to_html(child, self.current_page, self.docx, self.dest_dir):
                    text.add_elem(img)
                    ans.append(text.elem)
            elif is_tag(child, 'w:footnoteReference') or is_tag(child, 'w:endnoteReference'):
                anchor, name = self.footnotes.get_ref(child)
                if anchor and name:
                    l = SUP(A(name, href='#' + anchor, title=name), id='back_%s' % anchor)
                    l.set('class', 'noteref')
                    text.add_elem(l)
                    ans.append(text.elem)
        if text.buf:
            setattr(text.elem, text.attr, ''.join(text.buf))

        style = self.styles.resolve_run(run)
        if style.vert_align in {'superscript', 'subscript'}:
            ans.tag = 'sub' if style.vert_align == 'subscript' else 'sup'
        if style.lang is not inherit:
            ans.lang = style.lang
        return ans

    def add_frame(self, html_obj, style):
        last_run = self.framed[-1]
        if style is inherit:
            if last_run:
                self.framed.append([])
            return

        if last_run:
            if last_run[-1][1] == style:
                last_run.append((html_obj, style))
            else:
                self.framed.append((html_obj, style))
        else:
            last_run.append((html_obj, style))

    def apply_frames(self):
        for run in filter(None, self.framed):
            style = run[0][1]
            paras = tuple(x[0] for x in run)
            parent = paras[0].getparent()
            idx = parent.index(paras[0])
            frame = DIV(*paras)
            parent.insert(idx, frame)
            self.framed_map[frame] = css = style.css(self.page_map[self.object_map[paras[0]]])
            self.styles.register(css, 'frame')

if __name__ == '__main__':
    import shutil
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    dest_dir = os.path.join(os.getcwdu(), 'docx_input')
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.mkdir(dest_dir)
    Convert(sys.argv[-1], dest_dir=dest_dir, log=default_log)()

