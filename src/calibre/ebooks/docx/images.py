#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os

from lxml.html.builder import IMG, HR

from calibre.ebooks.docx.names import XPath, get, barename
from calibre.utils.filenames import ascii_filename
from calibre.utils.imghdr import what

def emu_to_pt(x):
    return x / 12700

def get_image_properties(parent):
    width = height = None
    for extent in XPath('./wp:extent')(parent):
        try:
            width = emu_to_pt(int(extent.get('cx')))
        except (TypeError, ValueError):
            pass
        try:
            height = emu_to_pt(int(extent.get('cy')))
        except (TypeError, ValueError):
            pass
    ans = {}
    if width is not None:
        ans['width'] = '%.3gpt' % width
    if height is not None:
        ans['height'] = '%.3gpt' % height

    alt = None
    for docPr in XPath('./wp:docPr')(parent):
        x = docPr.get('descr', None)
        if x:
            alt = x
        if docPr.get('hidden', None) in {'true', 'on', '1'}:
            ans['display'] = 'none'

    return ans, alt


def get_image_margins(elem):
    ans = {}
    for w, css in {'L':'left', 'T':'top', 'R':'right', 'B':'bottom'}.iteritems():
        val = elem.get('dist%s' % w, None)
        if val is not None:
            try:
                val = emu_to_pt(val)
            except (TypeError, ValueError):
                continue
            ans['padding-%s' % css] = '%.3gpt' % val
    return ans

def get_hpos(anchor, page_width):
    for ph in XPath('./wp:positionH')(anchor):
        rp = ph.get('relativeFrom', None)
        if rp == 'leftMargin':
            return 0
        if rp == 'rightMargin':
            return 1
        for align in XPath('./wp:align')(ph):
            al = align.text
            if al == 'left':
                return 0
            if al == 'center':
                return 0.5
            if al == 'right':
                return 1
        for po in XPath('./wp:posOffset')(ph):
            try:
                pos = emu_to_pt(int(po.text))
            except (TypeError, ValueError):
                continue
            return pos/page_width

    for sp in XPath('./wp:simplePos')(anchor):
        try:
            x = emu_to_pt(sp.get('x', None))
        except (TypeError, ValueError):
            continue
        return x/page_width

    return 0


class Images(object):

    def __init__(self, log):
        self.rid_map = {}
        self.used = {}
        self.names = set()
        self.all_images = set()
        self.links = []
        self.log = log

    def __call__(self, relationships_by_id):
        self.rid_map = relationships_by_id

    def generate_filename(self, rid, base=None, rid_map=None):
        rid_map = self.rid_map if rid_map is None else rid_map
        fname = rid_map[rid]
        if fname in self.used:
            return self.used[fname]
        raw = self.docx.read(fname)
        base = base or ascii_filename(rid_map[rid].rpartition('/')[-1]).replace(' ', '_') or 'image'
        ext = what(None, raw) or base.rpartition('.')[-1] or 'jpeg'
        if ext == 'emf':
            # For an example, see: https://bugs.launchpad.net/bugs/1224849
            self.log('Found an EMF image: %s, trying to extract embedded raster image' % base)
            from calibre.utils.wmf.emf import emf_unwrap
            try:
                raw = emf_unwrap(raw)
            except Exception as e:
                self.log.exception('Failed to extract embedded raster image from EMF')
            else:
                ext = 'png'

        base = base.rpartition('.')[0]
        if not base:
            base = 'image'
        base += '.' + ext
        exists = frozenset(self.used.itervalues())
        c = 1
        name = base
        while name in exists:
            n, e = base.rpartition('.')[0::2]
            name = '%s-%d.%s' % (n, c, e)
            c += 1
        self.used[fname] = name
        with open(os.path.join(self.dest_dir, name), 'wb') as f:
            f.write(raw)
        self.all_images.add('images/' + name)
        return name

    def pic_to_img(self, pic, alt, parent):
        name = None
        link = None
        for hl in XPath('descendant::a:hlinkClick[@r:id]')(parent):
            link = {'id':get(hl, 'r:id')}
            tgt = hl.get('tgtFrame', None)
            if tgt:
                link['target'] = tgt
            title = hl.get('tooltip', None)
            if title:
                link['title'] = title

        for pr in XPath('descendant::pic:cNvPr')(pic):
            name = pr.get('name', None)
            if name:
                name = ascii_filename(name).replace(' ', '_')
            alt = pr.get('descr', None)
            for a in XPath('descendant::a:blip[@r:embed]')(pic):
                rid = get(a, 'r:embed')
                if rid in self.rid_map:
                    src = self.generate_filename(rid, name)
                    img = IMG(src='images/%s' % src)
                    img.set('alt', alt or 'Image')
                    if link is not None:
                        self.links.append((img, link))
                    return img

    def drawing_to_html(self, drawing, page):
        # First process the inline pictures
        for inline in XPath('./wp:inline')(drawing):
            style, alt = get_image_properties(inline)
            for pic in XPath('descendant::pic:pic')(inline):
                ans = self.pic_to_img(pic, alt, inline)
                if ans is not None:
                    if style:
                        ans.set('style', '; '.join('%s: %s' % (k, v) for k, v in style.iteritems()))
                    yield ans

        # Now process the floats
        for anchor in XPath('./wp:anchor')(drawing):
            style, alt = get_image_properties(anchor)
            self.get_float_properties(anchor, style, page)
            for pic in XPath('descendant::pic:pic')(anchor):
                ans = self.pic_to_img(pic, alt, anchor)
                if ans is not None:
                    if style:
                        ans.set('style', '; '.join('%s: %s' % (k, v) for k, v in style.iteritems()))
                    yield ans

    def pict_to_html(self, pict, page):
        # First see if we have an <hr>
        is_hr = len(pict) == 1 and get(pict[0], 'o:hr') in {'t', 'true'}
        if is_hr:
            style = {}
            hr = HR()
            try:
                pct = float(get(pict[0], 'o:hrpct'))
            except (ValueError, TypeError, AttributeError):
                pass
            else:
                if pct > 0:
                    style['width'] = '%.3g%%' % pct
            align = get(pict[0], 'o:hralign', 'center')
            if align in {'left', 'right'}:
                style['margin-left'] = '0' if align == 'left' else 'auto'
                style['margin-right'] = 'auto' if align == 'left' else '0'
            if style:
                hr.set('style', '; '.join(('%s:%s' % (k, v) for k, v in style.iteritems())))
            yield hr

        for imagedata in XPath('descendant::v:imagedata[@r:id]')(pict):
            rid = get(imagedata, 'r:id')
            if rid in self.rid_map:
                src = self.generate_filename(rid)
                img = IMG(src='images/%s' % src, style="display:block")
                alt = get(imagedata, 'o:title')
                img.set('alt', alt or 'Image')
                yield img

    def get_float_properties(self, anchor, style, page):
        if 'display' not in style:
            style['display'] = 'block'
        padding = get_image_margins(anchor)
        width = float(style.get('width', '100pt')[:-2])

        page_width = page.width - page.margin_left - page.margin_right

        hpos = get_hpos(anchor, page_width) + width/(2*page_width)

        wrap_elem = None
        dofloat = False

        for child in reversed(anchor):
            bt = barename(child.tag)
            if bt in {'wrapNone', 'wrapSquare', 'wrapThrough', 'wrapTight', 'wrapTopAndBottom'}:
                wrap_elem = child
                dofloat = bt not in {'wrapNone', 'wrapTopAndBottom'}
                break

        if wrap_elem is not None:
            padding.update(get_image_margins(wrap_elem))
            wt = wrap_elem.get('wrapText', None)
            hpos = 0 if wt == 'right' else 1 if wt == 'left' else hpos
            if dofloat:
                style['float'] = 'left' if hpos < 0.65 else 'right'
            else:
                ml, mr = (None, None) if hpos < 0.34 else ('auto', None) if hpos > 0.65 else ('auto', 'auto')
                if ml is not None:
                    style['margin-left'] = ml
                if mr is not None:
                    style['margin-right'] = mr

        style.update(padding)

    def to_html(self, elem, page, docx, dest_dir):
        dest = os.path.join(dest_dir, 'images')
        if not os.path.exists(dest):
            os.mkdir(dest)
        self.dest_dir, self.docx = dest, docx
        if elem.tag.endswith('}drawing'):
            for tag in self.drawing_to_html(elem, page):
                yield tag
        else:
            for tag in self.pict_to_html(elem, page):
                yield tag


