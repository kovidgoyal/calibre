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
    descendants, FOOTNOTES, ENDNOTES, children, THEMES)
from calibre.ebooks.docx.styles import Styles, inherit, PageProperties
from calibre.ebooks.docx.numbering import Numbering
from calibre.ebooks.docx.fonts import Fonts
from calibre.ebooks.docx.images import Images
from calibre.ebooks.docx.tables import Tables
from calibre.ebooks.docx.footnotes import Footnotes
from calibre.ebooks.docx.cleanup import cleanup_markup
from calibre.ebooks.docx.theme import Theme
from calibre.ebooks.docx.toc import create_toc
from calibre.ebooks.docx.fields import Fields
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1

class Text:

    def __init__(self, elem, attr, buf):
        self.elem, self.attr, self.buf = elem, attr, buf

    def add_elem(self, elem):
        setattr(self.elem, self.attr, ''.join(self.buf))
        self.elem, self.attr, self.buf = elem, 'tail', []

class Convert(object):

    def __init__(self, path_or_stream, dest_dir=None, log=None, detect_cover=True, notes_text=None):
        self.docx = DOCX(path_or_stream, log=log)
        self.ms_pat = re.compile(r'\s{2,}')
        self.ws_pat = re.compile(r'[\n\r\t]')
        self.log = self.docx.log
        self.detect_cover = detect_cover
        self.notes_text = notes_text or _('Notes')
        self.dest_dir = dest_dir or os.getcwdu()
        self.mi = self.docx.metadata
        self.body = BODY()
        self.theme = Theme()
        self.tables = Tables()
        self.fields = Fields()
        self.styles = Styles(self.tables)
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
        self.fields(doc, self.log)
        self.read_styles(relationships_by_type)
        self.images(relationships_by_id)
        self.layers = OrderedDict()
        self.framed = [[]]
        self.framed_map = {}
        self.anchor_map = {}
        self.link_map = defaultdict(list)
        paras = []

        self.log.debug('Converting Word markup to HTML')
        self.read_page_properties(doc)
        for wp, page_properties in self.page_map.iteritems():
            self.current_page = page_properties
            if wp.tag.endswith('}p'):
                p = self.convert_p(wp)
                self.body.append(p)
                paras.append(wp)
        self.read_block_anchors(doc)
        self.styles.apply_contextual_spacing(paras)
        # Apply page breaks at the start of every section, except the first
        # section (since that will be the start of the file)
        self.styles.apply_section_page_breaks(self.section_starts[1:])

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
                paras = []
                for wp in note:
                    if wp.tag.endswith('}tbl'):
                        self.tables.register(wp, self.styles)
                        self.page_map[wp] = self.current_page
                    else:
                        p = self.convert_p(wp)
                        dl[-1].append(p)
                        paras.append(wp)
                self.styles.apply_contextual_spacing(paras)

        self.resolve_links(relationships_by_id)

        self.styles.cascade(self.layers)

        self.tables.apply_markup(self.object_map, self.page_map)

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
        self.numbering.apply_markup(numbered, self.body, self.styles, self.object_map, self.images)
        self.apply_frames()

        if len(self.body) > 0:
            self.body.text = '\n\t'
            for child in self.body:
                child.tail = '\n\t'
            self.body[-1].tail = '\n'

        self.log.debug('Converting styles to CSS')
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
            for h in children(self.body, 'h1', 'h2', 'h3'):
                notes_header.tag = h.tag
                cls = h.get('class', None)
                if cls and cls != 'notes-header':
                    notes_header.set('class', '%s notes-header' % cls)
                break

        self.log.debug('Cleaning up redundant markup generated by Word')
        self.cover_image = cleanup_markup(self.log, self.html, self.styles, self.dest_dir, self.detect_cover)

        return self.write(doc)

    def read_page_properties(self, doc):
        current = []
        self.page_map = OrderedDict()
        self.section_starts = []

        for p in descendants(doc, 'w:p', 'w:tbl'):
            if p.tag.endswith('}tbl'):
                self.tables.register(p, self.styles)
                current.append(p)
                continue
            sect = tuple(descendants(p, 'w:sectPr'))
            if sect:
                pr = PageProperties(sect)
                paras = current + [p]
                for x in paras:
                    self.page_map[x] = pr
                self.section_starts.append(paras[0])
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
        tname = get_name(THEMES, 'theme1.xml')
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

        if tname is not None:
            try:
                raw = self.docx.read(tname)
            except KeyError:
                self.log.warn('Styles %s do not exist' % sname)
            else:
                self.theme(fromstring(raw))

        if sname is not None:
            try:
                raw = self.docx.read(sname)
            except KeyError:
                self.log.warn('Styles %s do not exist' % sname)
            else:
                self.styles(fromstring(raw), fonts, self.theme)

        if nname is not None:
            try:
                raw = self.docx.read(nname)
            except KeyError:
                self.log.warn('Numbering styles %s do not exist' % nname)
            else:
                numbering(fromstring(raw), self.styles, self.docx.get_relationships(nname)[0])

        self.styles.resolve_numbering(numbering)

    def write(self, doc):
        toc = create_toc(doc, self.body, self.resolved_link_map, self.styles, self.object_map)
        raw = html.tostring(self.html, encoding='utf-8', doctype='<!DOCTYPE html>')
        with open(os.path.join(self.dest_dir, 'index.html'), 'wb') as f:
            f.write(raw)
        css = self.styles.generate_css(self.dest_dir, self.docx)
        if css:
            with open(os.path.join(self.dest_dir, 'docx.css'), 'wb') as f:
                f.write(css.encode('utf-8'))

        opf = OPFCreator(self.dest_dir, self.mi)
        opf.toc = toc
        opf.create_manifest_from_files_in([self.dest_dir])
        opf.create_spine(['index.html'])
        if self.cover_image is not None:
            opf.guide.set_cover(self.cover_image)
        with open(os.path.join(self.dest_dir, 'metadata.opf'), 'wb') as of, open(os.path.join(self.dest_dir, 'toc.ncx'), 'wb') as ncx:
            opf.render(of, ncx, 'toc.ncx')
        return os.path.join(self.dest_dir, 'metadata.opf')

    def read_block_anchors(self, doc):
        doc_anchors = frozenset(XPath('./w:body/w:bookmarkStart[@w:name]')(doc))
        if doc_anchors:
            current_bm = None
            rmap = {v:k for k, v in self.object_map.iteritems()}
            for p in descendants(doc, 'w:p', 'w:bookmarkStart[@w:name]'):
                if p.tag.endswith('}p'):
                    if current_bm and p in rmap:
                        para = rmap[p]
                        if 'id' not in para.attrib:
                            para.set('id', generate_anchor(current_bm, frozenset(self.anchor_map.itervalues())))
                        self.anchor_map[current_bm] = para.get('id')
                        current_bm = None
                elif p in doc_anchors:
                    current_bm = get(p, 'w:name')

    def convert_p(self, p):
        dest = P()
        self.object_map[dest] = p
        style = self.styles.resolve_paragraph(p)
        self.layers[p] = []
        self.add_frame(dest, style.frame)

        current_anchor = None
        current_hyperlink = None
        hl_xpath = XPath('ancestor::w:hyperlink[1]')

        for x in descendants(p, 'w:r', 'w:bookmarkStart', 'w:hyperlink'):
            if x.tag.endswith('}r'):
                span = self.convert_run(x)
                if current_anchor is not None:
                    (dest if len(dest) == 0 else span).set('id', current_anchor)
                    current_anchor = None
                if current_hyperlink is not None:
                    try:
                        hl = hl_xpath(x)[0]
                        self.link_map[hl].append(span)
                        x.set('is-link', '1')
                    except IndexError:
                        current_hyperlink = None
                dest.append(span)
                self.layers[p].append(x)
            elif x.tag.endswith('}bookmarkStart'):
                anchor = get(x, 'w:name')
                if anchor and anchor not in self.anchor_map:
                    old_anchor = current_anchor
                    self.anchor_map[anchor] = current_anchor = generate_anchor(anchor, frozenset(self.anchor_map.itervalues()))
                    if old_anchor is not None:
                        # The previous anchor was not applied to any element
                        for a, t in tuple(self.anchor_map.iteritems()):
                            if t == old_anchor:
                                self.anchor_map[a] = current_anchor
            elif x.tag.endswith('}hyperlink'):
                current_hyperlink = x

        m = re.match(r'heading\s+(\d+)$', style.style_name or '', re.IGNORECASE)
        if m is not None:
            n = min(6, max(1, int(m.group(1))))
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

        if not dest.text and len(dest) == 0:
            # Empty paragraph add a non-breaking space so that it is rendered
            # by WebKit
            dest.text = '\xa0'
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
        self.resolved_link_map = {}
        for hyperlink, spans in self.link_map.iteritems():
            span = spans[0]
            if len(spans) > 1:
                span = self.wrap_elems(spans, SPAN())
            span.tag = 'a'
            self.resolved_link_map[hyperlink] = span
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
            self.log.warn('Hyperlink with unknown target (rid=%s, anchor=%s), ignoring' %
                          (rid, anchor))
            # hrefs that point nowhere give epubcheck a hernia. The element
            # should be styled explicitly by Word anyway.
            # span.set('href', '#')
        rmap = {v:k for k, v in self.object_map.iteritems()}
        for hyperlink, runs in self.fields.hyperlink_fields:
            spans = [rmap[r] for r in runs if r in rmap]
            if not spans:
                continue
            if len(spans) > 1:
                span = self.wrap_elems(spans, SPAN())
            span.tag = 'a'
            tgt = hyperlink.get('target', None)
            if tgt:
                span.set('target', tgt)
            tt = hyperlink.get('title', None)
            if tt:
                span.set('title', tt)
            url = hyperlink['url']
            if url in self.anchor_map:
                span.set('href', '#' + self.anchor_map[url])
                continue
            span.set('href', url)

        for img, link in self.images.links:
            parent = img.getparent()
            idx = parent.index(img)
            a = A(img)
            a.tail, img.tail = img.tail, None
            parent.insert(idx, a)
            tgt = link.get('target', None)
            if tgt:
                a.set('target', tgt)
            tt = link.get('title', None)
            if tt:
                a.set('title', tt)
            rid = link['id']
            if rid in relationships_by_id:
                dest = relationships_by_id[rid]
                if dest.startswith('#'):
                    if dest[1:] in self.anchor_map:
                        a.set('href', '#' + self.anchor_map[dest[1:]])
                else:
                    a.set('href', dest)

    def convert_run(self, run):
        ans = SPAN()
        self.object_map[ans] = run
        text = Text(ans, 'text', [])

        for child in run:
            if is_tag(child, 'w:t'):
                if not child.text:
                    continue
                space = child.get(XML('space'), None)
                preserve = False
                if space == 'preserve':
                    # Only use a <span> with white-space:pre-wrap if this element
                    # actually needs it, i.e. if it has more than one
                    # consecutive space or it has newlines or tabs.
                    multi_spaces = self.ms_pat.search(child.text) is not None
                    preserve = multi_spaces or self.ws_pat.search(child.text) is not None
                if preserve:
                    text.add_elem(SPAN(child.text, style="white-space:pre-wrap"))
                    ans.append(text.elem)
                else:
                    text.buf.append(child.text)
            elif is_tag(child, 'w:cr'):
                text.add_elem(BR())
                ans.append(text.elem)
            elif is_tag(child, 'w:br'):
                typ = get(child, 'w:type')
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

