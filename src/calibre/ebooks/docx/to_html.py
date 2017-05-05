#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, re, math, errno, uuid
from collections import OrderedDict, defaultdict

from lxml import html
from lxml.html.builder import (
    HTML, HEAD, TITLE, BODY, LINK, META, P, SPAN, BR, DIV, SUP, A, DT, DL, DD, H1)

from calibre import guess_type
from calibre.ebooks.docx.container import DOCX, fromstring
from calibre.ebooks.docx.names import XML, generate_anchor
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
from calibre.ebooks.docx.settings import Settings
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1

NBSP = '\xa0'


class Text:

    def __init__(self, elem, attr, buf):
        self.elem, self.attr, self.buf = elem, attr, buf

    def add_elem(self, elem):
        setattr(self.elem, self.attr, ''.join(self.buf))
        self.elem, self.attr, self.buf = elem, 'tail', []


def html_lang(docx_lang):
    lang = canonicalize_lang(docx_lang)
    if lang and lang != 'und':
        lang = lang_as_iso639_1(lang)
        if lang:
            return lang


class Convert(object):

    def __init__(self, path_or_stream, dest_dir=None, log=None, detect_cover=True, notes_text=None, notes_nopb=False, nosupsub=False):
        self.docx = DOCX(path_or_stream, log=log)
        self.namespace = self.docx.namespace
        self.ms_pat = re.compile(r'\s{2,}')
        self.ws_pat = re.compile(r'[\n\r\t]')
        self.log = self.docx.log
        self.detect_cover = detect_cover
        self.notes_text = notes_text or _('Notes')
        self.notes_nopb = notes_nopb
        self.nosupsub = nosupsub
        self.dest_dir = dest_dir or os.getcwdu()
        self.mi = self.docx.metadata
        self.body = BODY()
        self.theme = Theme(self.namespace)
        self.settings = Settings(self.namespace)
        self.tables = Tables(self.namespace)
        self.fields = Fields(self.namespace)
        self.styles = Styles(self.namespace, self.tables)
        self.images = Images(self.namespace, self.log)
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
        lang = html_lang(self.mi.language)
        if lang:
            self.html.set('lang', lang)
            self.doc_lang = lang
        else:
            self.doc_lang = None

    def __call__(self):
        doc = self.docx.document
        relationships_by_id, relationships_by_type = self.docx.document_relationships
        self.fields(doc, self.log)
        self.read_styles(relationships_by_type)
        self.images(relationships_by_id)
        self.layers = OrderedDict()
        self.framed = [[]]
        self.frame_map = {}
        self.framed_map = {}
        self.anchor_map = {}
        self.link_map = defaultdict(list)
        self.link_source_map = {}
        self.toc_anchor = None
        self.block_runs = []
        paras = []

        self.log.debug('Converting Word markup to HTML')

        self.read_page_properties(doc)
        self.current_rels = relationships_by_id
        for wp, page_properties in self.page_map.iteritems():
            self.current_page = page_properties
            if wp.tag.endswith('}p'):
                p = self.convert_p(wp)
                self.body.append(p)
                paras.append(wp)

        self.read_block_anchors(doc)
        self.styles.apply_contextual_spacing(paras)
        self.mark_block_runs(paras)
        # Apply page breaks at the start of every section, except the first
        # section (since that will be the start of the file)
        self.styles.apply_section_page_breaks(self.section_starts[1:])

        notes_header = None
        orig_rid_map = self.images.rid_map
        if self.footnotes.has_notes:
            self.body.append(H1(self.notes_text))
            notes_header = self.body[-1]
            notes_header.set('class', 'notes-header')
            for anchor, text, note in self.footnotes:
                dl = DL(id=anchor)
                dl.set('class', 'footnote')
                self.body.append(dl)
                dl.append(DT('[', A('←' + text, href='#back_%s' % anchor, title=text)))
                dl[-1][0].tail = ']'
                dl.append(DD())
                paras = []
                self.images.rid_map = self.current_rels = note.rels[0]
                for wp in note:
                    if wp.tag.endswith('}tbl'):
                        self.tables.register(wp, self.styles)
                        self.page_map[wp] = self.current_page
                    else:
                        p = self.convert_p(wp)
                        dl[-1].append(p)
                        paras.append(wp)
                self.styles.apply_contextual_spacing(paras)
                self.mark_block_runs(paras)

        for p, wp in self.object_map.iteritems():
            if len(p) > 0 and not p.text and len(p[0]) > 0 and not p[0].text and p[0][0].get('class', None) == 'tab':
                # Paragraph uses tabs for indentation, convert to text-indent
                parent = p[0]
                tabs = []
                for child in parent:
                    if child.get('class', None) == 'tab':
                        tabs.append(child)
                        if child.tail:
                            break
                    else:
                        break
                indent = len(tabs) * self.settings.default_tab_stop
                style = self.styles.resolve(wp)
                if style.text_indent is inherit or (hasattr(style.text_indent, 'endswith') and style.text_indent.endswith('pt')):
                    if style.text_indent is not inherit:
                        indent = float(style.text_indent[:-2]) + indent
                    style.text_indent = '%.3gpt' % indent
                    parent.text = tabs[-1].tail or ''
                    map(parent.remove, tabs)

        self.images.rid_map = orig_rid_map

        self.resolve_links()

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
            for h in self.namespace.children(self.body, 'h1', 'h2', 'h3'):
                notes_header.tag = h.tag
                cls = h.get('class', None)
                if cls and cls != 'notes-header':
                    notes_header.set('class', '%s notes-header' % cls)
                break

        self.fields.polish_markup(self.object_map)

        self.log.debug('Cleaning up redundant markup generated by Word')
        self.cover_image = cleanup_markup(self.log, self.html, self.styles, self.dest_dir, self.detect_cover, self.namespace.XPath)

        return self.write(doc)

    def read_page_properties(self, doc):
        current = []
        self.page_map = OrderedDict()
        self.section_starts = []

        for p in self.namespace.descendants(doc, 'w:p', 'w:tbl'):
            if p.tag.endswith('}tbl'):
                self.tables.register(p, self.styles)
                current.append(p)
                continue
            sect = tuple(self.namespace.descendants(p, 'w:sectPr'))
            if sect:
                pr = PageProperties(self.namespace, sect)
                paras = current + [p]
                for x in paras:
                    self.page_map[x] = pr
                self.section_starts.append(paras[0])
                current = []
            else:
                current.append(p)

        if current:
            self.section_starts.append(current[0])
            last = self.namespace.XPath('./w:body/w:sectPr')(doc)
            pr = PageProperties(self.namespace, last)
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

        nname = get_name(self.namespace.names['NUMBERING'], 'numbering.xml')
        sname = get_name(self.namespace.names['STYLES'], 'styles.xml')
        sename = get_name(self.namespace.names['SETTINGS'], 'settings.xml')
        fname = get_name(self.namespace.names['FONTS'], 'fontTable.xml')
        tname = get_name(self.namespace.names['THEMES'], 'theme1.xml')
        foname = get_name(self.namespace.names['FOOTNOTES'], 'footnotes.xml')
        enname = get_name(self.namespace.names['ENDNOTES'], 'endnotes.xml')
        numbering = self.numbering = Numbering(self.namespace)
        footnotes = self.footnotes = Footnotes(self.namespace)
        fonts = self.fonts = Fonts(self.namespace)

        foraw = enraw = None
        forel, enrel = ({}, {}), ({}, {})
        if sename is not None:
            try:
                seraw = self.docx.read(sename)
            except KeyError:
                self.log.warn('Settings %s do not exist' % sename)
            except EnvironmentError as e:
                if e.errno != errno.ENOENT:
                    raise
                self.log.warn('Settings %s file missing' % sename)
            else:
                self.settings(fromstring(seraw))

        if foname is not None:
            try:
                foraw = self.docx.read(foname)
            except KeyError:
                self.log.warn('Footnotes %s do not exist' % foname)
            else:
                forel = self.docx.get_relationships(foname)
        if enname is not None:
            try:
                enraw = self.docx.read(enname)
            except KeyError:
                self.log.warn('Endnotes %s do not exist' % enname)
            else:
                enrel = self.docx.get_relationships(enname)
        footnotes(fromstring(foraw) if foraw else None, forel, fromstring(enraw) if enraw else None, enrel)

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
        toc = create_toc(doc, self.body, self.resolved_link_map, self.styles, self.object_map, self.log, self.namespace)
        raw = html.tostring(self.html, encoding='utf-8', doctype='<!DOCTYPE html>')
        with lopen(os.path.join(self.dest_dir, 'index.html'), 'wb') as f:
            f.write(raw)
        css = self.styles.generate_css(self.dest_dir, self.docx, self.notes_nopb, self.nosupsub)
        if css:
            with lopen(os.path.join(self.dest_dir, 'docx.css'), 'wb') as f:
                f.write(css.encode('utf-8'))

        opf = OPFCreator(self.dest_dir, self.mi)
        opf.toc = toc
        opf.create_manifest_from_files_in([self.dest_dir])
        for item in opf.manifest:
            if item.media_type == 'text/html':
                item.media_type = guess_type('a.xhtml')[0]
        opf.create_spine(['index.html'])
        if self.cover_image is not None:
            opf.guide.set_cover(self.cover_image)

        def process_guide(E, guide):
            if self.toc_anchor is not None:
                guide.append(E.reference(
                    href='index.html#' + self.toc_anchor, title=_('Table of Contents'), type='toc'))
        toc_file = os.path.join(self.dest_dir, 'toc.ncx')
        with lopen(os.path.join(self.dest_dir, 'metadata.opf'), 'wb') as of, open(toc_file, 'wb') as ncx:
            opf.render(of, ncx, 'toc.ncx', process_guide=process_guide)
        if os.path.getsize(toc_file) == 0:
            os.remove(toc_file)
        return os.path.join(self.dest_dir, 'metadata.opf')

    def read_block_anchors(self, doc):
        doc_anchors = frozenset(self.namespace.XPath('./w:body/w:bookmarkStart[@w:name]')(doc))
        if doc_anchors:
            current_bm = set()
            rmap = {v:k for k, v in self.object_map.iteritems()}
            for p in self.namespace.descendants(doc, 'w:p', 'w:bookmarkStart[@w:name]'):
                if p.tag.endswith('}p'):
                    if current_bm and p in rmap:
                        para = rmap[p]
                        if 'id' not in para.attrib:
                            para.set('id', generate_anchor(next(iter(current_bm)), frozenset(self.anchor_map.itervalues())))
                        for name in current_bm:
                            self.anchor_map[name] = para.get('id')
                        current_bm = set()
                elif p in doc_anchors:
                    anchor = self.namespace.get(p, 'w:name')
                    if anchor:
                        current_bm.add(anchor)

    def convert_p(self, p):
        dest = P()
        self.object_map[dest] = p
        style = self.styles.resolve_paragraph(p)
        self.layers[p] = []
        self.frame_map[p] = style.frame
        self.add_frame(dest, style.frame)

        current_anchor = None
        current_hyperlink = None
        hl_xpath = self.namespace.XPath('ancestor::w:hyperlink[1]')

        def p_parent(x):
            # Ensure that nested <w:p> tags are handled. These can occur if a
            # textbox is present inside a paragraph.
            while True:
                x = x.getparent()
                try:
                    if x.tag.endswith('}p'):
                        return x
                except AttributeError:
                    break

        for x in self.namespace.descendants(p, 'w:r', 'w:bookmarkStart', 'w:hyperlink', 'w:instrText'):
            if p_parent(x) is not p:
                continue
            if x.tag.endswith('}r'):
                span = self.convert_run(x)
                if current_anchor is not None:
                    (dest if len(dest) == 0 else span).set('id', current_anchor)
                    current_anchor = None
                if current_hyperlink is not None:
                    try:
                        hl = hl_xpath(x)[0]
                        self.link_map[hl].append(span)
                        self.link_source_map[hl] = self.current_rels
                        x.set('is-link', '1')
                    except IndexError:
                        current_hyperlink = None
                dest.append(span)
                self.layers[p].append(x)
            elif x.tag.endswith('}bookmarkStart'):
                anchor = self.namespace.get(x, 'w:name')
                if anchor and anchor not in self.anchor_map and anchor != '_GoBack':
                    # _GoBack is a special bookmark inserted by Word 2010 for
                    # the return to previous edit feature, we ignore it
                    old_anchor = current_anchor
                    self.anchor_map[anchor] = current_anchor = generate_anchor(anchor, frozenset(self.anchor_map.itervalues()))
                    if old_anchor is not None:
                        # The previous anchor was not applied to any element
                        for a, t in tuple(self.anchor_map.iteritems()):
                            if t == old_anchor:
                                self.anchor_map[a] = current_anchor
            elif x.tag.endswith('}hyperlink'):
                current_hyperlink = x
            elif x.tag.endswith('}instrText') and x.text and x.text.strip().startswith('TOC '):
                old_anchor = current_anchor
                anchor = str(uuid.uuid4())
                self.anchor_map[anchor] = current_anchor = generate_anchor('toc', frozenset(self.anchor_map.itervalues()))
                self.toc_anchor = current_anchor
                if old_anchor is not None:
                    # The previous anchor was not applied to any element
                    for a, t in tuple(self.anchor_map.iteritems()):
                        if t == old_anchor:
                            self.anchor_map[a] = current_anchor
        if current_anchor is not None:
            # This paragraph had no <w:r> descendants
            dest.set('id', current_anchor)
            current_anchor = None

        m = re.match(r'heading\s+(\d+)$', style.style_name or '', re.IGNORECASE)
        if m is not None:
            n = min(6, max(1, int(m.group(1))))
            dest.tag = 'h%d' % n

        if style.bidi is True:
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

        if not dest.text and len(dest) == 0 and not style.has_visible_border():
            # Empty paragraph add a non-breaking space so that it is rendered
            # by WebKit
            dest.text = NBSP

        # If the last element in a block is a <br> the <br> is not rendered in
        # HTML, unless it is followed by a trailing space. Word, on the other
        # hand inserts a blank line for trailing <br>s.
        if len(dest) > 0 and not dest[-1].tail:
            if dest[-1].tag == 'br':
                dest[-1].tail = NBSP
            elif len(dest[-1]) > 0 and dest[-1][-1].tag == 'br' and not dest[-1][-1].tail:
                dest[-1][-1].tail = NBSP

        return dest

    def wrap_elems(self, elems, wrapper):
        p = elems[0].getparent()
        idx = p.index(elems[0])
        p.insert(idx, wrapper)
        wrapper.tail = elems[-1].tail
        elems[-1].tail = None
        for elem in elems:
            try:
                p.remove(elem)
            except ValueError:
                # Probably a hyperlink that spans multiple
                # paragraphs,theoretically we should break this up into
                # multiple hyperlinks, but I can't be bothered.
                elem.getparent().remove(elem)
            wrapper.append(elem)
        return wrapper

    def resolve_links(self):
        self.resolved_link_map = {}
        for hyperlink, spans in self.link_map.iteritems():
            relationships_by_id = self.link_source_map[hyperlink]
            span = spans[0]
            if len(spans) > 1:
                span = self.wrap_elems(spans, SPAN())
            span.tag = 'a'
            self.resolved_link_map[hyperlink] = span
            tgt = self.namespace.get(hyperlink, 'w:tgtFrame')
            if tgt:
                span.set('target', tgt)
            tt = self.namespace.get(hyperlink, 'w:tooltip')
            if tt:
                span.set('title', tt)
            rid = self.namespace.get(hyperlink, 'r:id')
            if rid and rid in relationships_by_id:
                span.set('href', relationships_by_id[rid])
                continue
            anchor = self.namespace.get(hyperlink, 'w:anchor')
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
            span = spans[0]
            if len(spans) > 1:
                span = self.wrap_elems(spans, SPAN())
            span.tag = 'a'
            tgt = hyperlink.get('target', None)
            if tgt:
                span.set('target', tgt)
            tt = hyperlink.get('title', None)
            if tt:
                span.set('title', tt)
            url = hyperlink.get('url', None)
            if url is None:
                anchor = hyperlink.get('anchor', None)
                if anchor in self.anchor_map:
                    span.set('href', '#' + self.anchor_map[anchor])
                    continue
                self.log.warn('Hyperlink field with unknown anchor: %s' % anchor)
            else:
                if url in self.anchor_map:
                    span.set('href', '#' + self.anchor_map[url])
                    continue
                span.set('href', url)

        for img, link, relationships_by_id in self.images.links:
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
            if self.namespace.is_tag(child, 'w:t'):
                if not child.text:
                    continue
                space = child.get(XML('space'), None)
                preserve = False
                ctext = child.text
                if space != 'preserve':
                    # Remove leading and trailing whitespace. Word ignores
                    # leading and trailing whitespace without preserve
                    ctext = ctext.strip(' \n\r\t')
                # Only use a <span> with white-space:pre-wrap if this element
                # actually needs it, i.e. if it has more than one
                # consecutive space or it has newlines or tabs.
                multi_spaces = self.ms_pat.search(ctext) is not None
                preserve = multi_spaces or self.ws_pat.search(ctext) is not None
                if preserve:
                    text.add_elem(SPAN(ctext, style="white-space:pre-wrap"))
                    ans.append(text.elem)
                else:
                    text.buf.append(ctext)
            elif self.namespace.is_tag(child, 'w:cr'):
                text.add_elem(BR())
                ans.append(text.elem)
            elif self.namespace.is_tag(child, 'w:br'):
                typ = self.namespace.get(child, 'w:type')
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
            elif self.namespace.is_tag(child, 'w:drawing') or self.namespace.is_tag(child, 'w:pict'):
                for img in self.images.to_html(child, self.current_page, self.docx, self.dest_dir):
                    text.add_elem(img)
                    ans.append(text.elem)
            elif self.namespace.is_tag(child, 'w:footnoteReference') or self.namespace.is_tag(child, 'w:endnoteReference'):
                anchor, name = self.footnotes.get_ref(child)
                if anchor and name:
                    l = A(SUP(name, id='back_%s' % anchor), href='#' + anchor, title=name)
                    l.set('class', 'noteref')
                    text.add_elem(l)
                    ans.append(text.elem)
            elif self.namespace.is_tag(child, 'w:tab'):
                spaces = int(math.ceil((self.settings.default_tab_stop / 36) * 6))
                text.add_elem(SPAN(NBSP * spaces))
                ans.append(text.elem)
                ans[-1].set('class', 'tab')
            elif self.namespace.is_tag(child, 'w:noBreakHyphen'):
                text.buf.append(u'\u2011')
            elif self.namespace.is_tag(child, 'w:softHyphen'):
                text.buf.append(u'\u00ad')
        if text.buf:
            setattr(text.elem, text.attr, ''.join(text.buf))

        style = self.styles.resolve_run(run)
        if style.vert_align in {'superscript', 'subscript'}:
            ans.tag = 'sub' if style.vert_align == 'subscript' else 'sup'
        if style.lang is not inherit:
            lang = html_lang(style.lang)
            if lang is not None and lang != self.doc_lang:
                ans.set('lang', lang)
        if style.rtl is True:
            ans.set('dir', 'rtl')
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
                self.framed[-1].append((html_obj, style))
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

        if not self.block_runs:
            return
        rmap = {v:k for k, v in self.object_map.iteritems()}
        for border_style, blocks in self.block_runs:
            paras = tuple(rmap[p] for p in blocks)
            parent = paras[0].getparent()
            idx = parent.index(paras[0])
            frame = DIV(*paras)
            parent.insert(idx, frame)
            self.framed_map[frame] = css = border_style.css
            self.styles.register(css, 'frame')

    def mark_block_runs(self, paras):

        def process_run(run):
            max_left = max_right = 0
            has_visible_border = None
            for p in run:
                style = self.styles.resolve_paragraph(p)
                if has_visible_border is None:
                    has_visible_border = style.has_visible_border()
                max_left, max_right = max(style.margin_left, max_left), max(style.margin_right, max_right)
                if has_visible_border:
                    style.margin_left = style.margin_right = inherit
                if p is not run[0]:
                    style.padding_top = 0
                else:
                    border_style = style.clone_border_styles()
                    if has_visible_border:
                        border_style.margin_top, style.margin_top = style.margin_top, inherit
                if p is not run[-1]:
                    style.padding_bottom = 0
                else:
                    if has_visible_border:
                        border_style.margin_bottom, style.margin_bottom = style.margin_bottom, inherit
                style.clear_borders()
                if p is not run[-1]:
                    style.apply_between_border()
            if has_visible_border:
                border_style.margin_left, border_style.margin_right = max_left,max_right
                self.block_runs.append((border_style, run))

        run = []
        for p in paras:
            if run and self.frame_map.get(p) == self.frame_map.get(run[-1]):
                style = self.styles.resolve_paragraph(p)
                last_style = self.styles.resolve_paragraph(run[-1])
                if style.has_identical_borders(last_style):
                    run.append(p)
                    continue
            if len(run) > 1:
                process_run(run)
            run = [p]
        if len(run) > 1:
            process_run(run)


if __name__ == '__main__':
    import shutil
    from calibre.utils.logging import default_log
    default_log.filter_level = default_log.DEBUG
    dest_dir = os.path.join(os.getcwdu(), 'docx_input')
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.mkdir(dest_dir)
    Convert(sys.argv[-1], dest_dir=dest_dir, log=default_log)()
