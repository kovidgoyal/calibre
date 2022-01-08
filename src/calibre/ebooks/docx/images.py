#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import re
from lxml.html.builder import HR, IMG

from calibre import sanitize_file_name
from calibre.constants import iswindows
from calibre.ebooks.docx.names import barename
from calibre.utils.filenames import ascii_filename
from calibre.utils.img import image_to_data, resize_to_fit
from calibre.utils.imghdr import what
from polyglot.builtins import iteritems, itervalues


class LinkedImageNotFound(ValueError):

    def __init__(self, fname):
        ValueError.__init__(self, fname)
        self.fname = fname


def image_filename(x):
    return sanitize_file_name(re.sub(r'[^0-9a-zA-Z.-]', '_', ascii_filename(x)).lstrip('_').lstrip('.'))


def emu_to_pt(x):
    return x / 12700


def pt_to_emu(x):
    return int(x * 12700)


def get_image_properties(parent, XPath, get):
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
    title = None
    for docPr in XPath('./wp:docPr')(parent):
        alt = docPr.get('descr') or alt
        title = docPr.get('title') or title
        if docPr.get('hidden', None) in {'true', 'on', '1'}:
            ans['display'] = 'none'
    transforms = []
    for graphic in XPath('./a:graphic')(parent):
        for xfrm in XPath('descendant::a:xfrm')(graphic):
            rot = xfrm.get('rot')
            if rot:
                try:
                    rot = int(rot) / 60000
                except Exception:
                    rot = None
            if rot:
                transforms.append(f'rotate({rot:g}deg)')
            fliph = xfrm.get('flipH')
            if fliph in ('1', 'true'):
                transforms.append('scaleX(-1)')
            flipv = xfrm.get('flipV')
            if flipv in ('1', 'true'):
                transforms.append('scaleY(-1)')

    if transforms:
        ans['transform'] = ' '.join(transforms)

    return ans, alt, title


def get_image_margins(elem):
    ans = {}
    for w, css in iteritems({'L':'left', 'T':'top', 'R':'right', 'B':'bottom'}):
        val = elem.get('dist%s' % w, None)
        if val is not None:
            try:
                val = emu_to_pt(val)
            except (TypeError, ValueError):
                continue
            ans['padding-%s' % css] = '%.3gpt' % val
    return ans


def get_hpos(anchor, page_width, XPath, get, width_frac):
    for ph in XPath('./wp:positionH')(anchor):
        rp = ph.get('relativeFrom', None)
        if rp == 'leftMargin':
            return 0 + width_frac
        if rp == 'rightMargin':
            return 1 + width_frac
        al = None
        almap = {'left':0, 'center':0.5, 'right':1}
        for align in XPath('./wp:align')(ph):
            al = almap.get(align.text)
            if al is not None:
                if rp == 'page':
                    return al
                return al + width_frac
        for po in XPath('./wp:posOffset')(ph):
            try:
                pos = emu_to_pt(int(po.text))
            except (TypeError, ValueError):
                continue
            return pos/page_width + width_frac

    for sp in XPath('./wp:simplePos')(anchor):
        try:
            x = emu_to_pt(sp.get('x', None))
        except (TypeError, ValueError):
            continue
        return x/page_width + width_frac

    return 0


class Images:

    def __init__(self, namespace, log):
        self.namespace = namespace
        self.rid_map = {}
        self.used = {}
        self.resized = {}
        self.names = set()
        self.all_images = set()
        self.links = []
        self.log = log

    def __call__(self, relationships_by_id):
        self.rid_map = relationships_by_id

    def read_image_data(self, fname, base=None):
        if fname.startswith('file://'):
            src = fname[len('file://'):]
            if iswindows and src and src[0] == '/':
                src = src[1:]
            if not src or not os.path.exists(src):
                raise LinkedImageNotFound(src)
            with open(src, 'rb') as rawsrc:
                raw = rawsrc.read()
        else:
            try:
                raw = self.docx.read(fname)
            except KeyError:
                raise LinkedImageNotFound(fname)
        base = base or image_filename(fname.rpartition('/')[-1]) or 'image'
        ext = what(None, raw) or base.rpartition('.')[-1] or 'jpeg'
        if ext == 'emf':
            # For an example, see: https://bugs.launchpad.net/bugs/1224849
            self.log('Found an EMF image: %s, trying to extract embedded raster image' % fname)
            from calibre.utils.wmf.emf import emf_unwrap
            try:
                raw = emf_unwrap(raw)
            except Exception:
                self.log.exception('Failed to extract embedded raster image from EMF')
            else:
                ext = 'png'
        base = base.rpartition('.')[0]
        if not base:
            base = 'image'
        base += '.' + ext
        return raw, base

    def unique_name(self, base):
        exists = frozenset(itervalues(self.used))
        c = 1
        name = base
        while name in exists:
            n, e = base.rpartition('.')[0::2]
            name = '%s-%d.%s' % (n, c, e)
            c += 1
        return name

    def resize_image(self, raw, base, max_width, max_height):
        resized, img = resize_to_fit(raw, max_width, max_height)
        if resized:
            base, ext = os.path.splitext(base)
            base = base + '-%dx%d%s' % (max_width, max_height, ext)
            raw = image_to_data(img, fmt=ext[1:])
        return raw, base, resized

    def generate_filename(self, rid, base=None, rid_map=None, max_width=None, max_height=None):
        rid_map = self.rid_map if rid_map is None else rid_map
        fname = rid_map[rid]
        key = (fname, max_width, max_height)
        ans = self.used.get(key)
        if ans is not None:
            return ans
        raw, base = self.read_image_data(fname, base=base)
        resized = False
        if max_width is not None and max_height is not None:
            raw, base, resized = self.resize_image(raw, base, max_width, max_height)
        name = self.unique_name(base)
        self.used[key] = name
        if max_width is not None and max_height is not None and not resized:
            okey = (fname, None, None)
            if okey in self.used:
                return self.used[okey]
            self.used[okey] = name
        with open(os.path.join(self.dest_dir, name), 'wb') as f:
            f.write(raw)
        self.all_images.add('images/' + name)
        return name

    def pic_to_img(self, pic, alt, parent, title):
        XPath, get = self.namespace.XPath, self.namespace.get
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
                name = image_filename(name)
            alt = pr.get('descr') or alt
            for a in XPath('descendant::a:blip[@r:embed or @r:link]')(pic):
                rid = get(a, 'r:embed')
                if not rid:
                    rid = get(a, 'r:link')
                if rid and rid in self.rid_map:
                    try:
                        src = self.generate_filename(rid, name)
                    except LinkedImageNotFound as err:
                        self.log.warn('Linked image: %s not found, ignoring' % err.fname)
                        continue
                    img = IMG(src='images/%s' % src)
                    img.set('alt', alt or 'Image')
                    if title:
                        img.set('title', title)
                    if link is not None:
                        self.links.append((img, link, self.rid_map))
                    return img

    def drawing_to_html(self, drawing, page):
        XPath, get = self.namespace.XPath, self.namespace.get
        # First process the inline pictures
        for inline in XPath('./wp:inline')(drawing):
            style, alt, title = get_image_properties(inline, XPath, get)
            for pic in XPath('descendant::pic:pic')(inline):
                ans = self.pic_to_img(pic, alt, inline, title)
                if ans is not None:
                    if style:
                        ans.set('style', '; '.join(f'{k}: {v}' for k, v in iteritems(style)))
                    yield ans

        # Now process the floats
        for anchor in XPath('./wp:anchor')(drawing):
            style, alt, title = get_image_properties(anchor, XPath, get)
            self.get_float_properties(anchor, style, page)
            for pic in XPath('descendant::pic:pic')(anchor):
                ans = self.pic_to_img(pic, alt, anchor, title)
                if ans is not None:
                    if style:
                        ans.set('style', '; '.join(f'{k}: {v}' for k, v in iteritems(style)))
                    yield ans

    def pict_to_html(self, pict, page):
        XPath, get = self.namespace.XPath, self.namespace.get
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
                hr.set('style', '; '.join((f'{k}:{v}' for k, v in iteritems(style))))
            yield hr

        for imagedata in XPath('descendant::v:imagedata[@r:id]')(pict):
            rid = get(imagedata, 'r:id')
            if rid in self.rid_map:
                try:
                    src = self.generate_filename(rid)
                except LinkedImageNotFound as err:
                    self.log.warn('Linked image: %s not found, ignoring' % err.fname)
                    continue
                style = get(imagedata.getparent(), 'style')
                img = IMG(src='images/%s' % src)
                alt = get(imagedata, 'o:title')
                img.set('alt', alt or 'Image')
                if 'position:absolute' in style:
                    img.set('style', 'display: block')
                yield img

    def get_float_properties(self, anchor, style, page):
        XPath, get = self.namespace.XPath, self.namespace.get
        if 'display' not in style:
            style['display'] = 'block'
        padding = get_image_margins(anchor)
        width = float(style.get('width', '100pt')[:-2])

        page_width = page.width - page.margin_left - page.margin_right
        if page_width <= 0:
            # Ignore margins
            page_width = page.width

        hpos = get_hpos(anchor, page_width, XPath, get, width/(2*page_width))

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
            yield from self.drawing_to_html(elem, page)
        else:
            yield from self.pict_to_html(elem, page)
