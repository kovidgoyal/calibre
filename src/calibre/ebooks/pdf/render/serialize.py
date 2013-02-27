#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib
from future_builtins import map

from PyQt4.Qt import QBuffer, QByteArray, QImage, Qt, QColor, qRgba

from calibre.constants import (__appname__, __version__)
from calibre.ebooks.pdf.render.common import (
    Reference, EOL, serialize, Stream, Dictionary, String, Name, Array,
    fmtnum)
from calibre.ebooks.pdf.render.fonts import FontManager
from calibre.ebooks.pdf.render.links import Links
from calibre.utils.date import utcnow

PDFVER = b'%PDF-1.3'

class IndirectObjects(object):

    def __init__(self):
        self._list = []
        self._map = {}
        self._offsets = []

    def __len__(self):
        return len(self._list)

    def add(self, o):
        self._list.append(o)
        ref = Reference(len(self._list), o)
        self._map[id(o)] = ref
        self._offsets.append(None)
        return ref

    def commit(self, ref, stream):
        self.write_obj(stream, ref.num, ref.obj)

    def write_obj(self, stream, num, obj):
        stream.write(EOL)
        self._offsets[num-1] = stream.tell()
        stream.write('%d 0 obj'%num)
        stream.write(EOL)
        serialize(obj, stream)
        if stream.last_char != EOL:
            stream.write(EOL)
        stream.write('endobj')
        stream.write(EOL)

    def __getitem__(self, o):
        try:
            return self._map[id(self._list[o] if isinstance(o, int) else o)]
        except (KeyError, IndexError):
            raise KeyError('The object %r was not found'%o)

    def pdf_serialize(self, stream):
        for i, obj in enumerate(self._list):
            offset = self._offsets[i]
            if offset is None:
                self.write_obj(stream, i+1, obj)

    def write_xref(self, stream):
        self.xref_offset = stream.tell()
        stream.write(b'xref'+EOL)
        stream.write('0 %d'%(1+len(self._offsets)))
        stream.write(EOL)
        stream.write('%010d 65535 f '%0)
        stream.write(EOL)

        for offset in self._offsets:
            line = '%010d 00000 n '%offset
            stream.write(line.encode('ascii') + EOL)
        return self.xref_offset

class Page(Stream):

    def __init__(self, parentref, *args, **kwargs):
        super(Page, self).__init__(*args, **kwargs)
        self.page_dict = Dictionary({
            'Type': Name('Page'),
            'Parent': parentref,
        })
        self.opacities = {}
        self.fonts = {}
        self.xobjects = {}
        self.patterns = {}

    def set_opacity(self, opref):
        if opref not in self.opacities:
            self.opacities[opref] = 'Opa%d'%len(self.opacities)
        name = self.opacities[opref]
        serialize(Name(name), self)
        self.write(b' gs ')

    def add_font(self, fontref):
        if fontref not in self.fonts:
            self.fonts[fontref] = 'F%d'%len(self.fonts)
        return self.fonts[fontref]

    def add_image(self, imgref):
        if imgref not in self.xobjects:
            self.xobjects[imgref] = 'Image%d'%len(self.xobjects)
        return self.xobjects[imgref]

    def add_pattern(self, patternref):
        if patternref not in self.patterns:
            self.patterns[patternref] = 'Pat%d'%len(self.patterns)
        return self.patterns[patternref]

    def add_resources(self):
        r = Dictionary()
        if self.opacities:
            extgs = Dictionary()
            for opref, name in self.opacities.iteritems():
                extgs[name] = opref
            r['ExtGState'] = extgs
        if self.fonts:
            fonts = Dictionary()
            for ref, name in self.fonts.iteritems():
                fonts[name] = ref
            r['Font'] = fonts
        if self.xobjects:
            xobjects = Dictionary()
            for ref, name in self.xobjects.iteritems():
                xobjects[name] = ref
            r['XObject'] = xobjects
        if self.patterns:
            r['ColorSpace'] = Dictionary({'PCSp':Array(
                [Name('Pattern'), Name('DeviceRGB')])})
            patterns = Dictionary()
            for ref, name in self.patterns.iteritems():
                patterns[name] = ref
            r['Pattern'] = patterns
        if r:
            self.page_dict['Resources'] = r

    def end(self, objects, stream):
        contents = objects.add(self)
        objects.commit(contents, stream)
        self.page_dict['Contents'] = contents
        self.add_resources()
        ret = objects.add(self.page_dict)
        # objects.commit(ret, stream)
        return ret

class Path(object):

    def __init__(self):
        self.ops = []

    def move_to(self, x, y):
        self.ops.append((x, y, 'm'))

    def line_to(self, x, y):
        self.ops.append((x, y, 'l'))

    def curve_to(self, x1, y1, x2, y2, x, y):
        self.ops.append((x1, y1, x2, y2, x, y, 'c'))

    def close(self):
        self.ops.append(('h',))

class Catalog(Dictionary):

    def __init__(self, pagetree):
        super(Catalog, self).__init__({'Type':Name('Catalog'),
            'Pages': pagetree})

class PageTree(Dictionary):

    def __init__(self, page_size):
        super(PageTree, self).__init__({'Type':Name('Pages'),
            'MediaBox':Array([0, 0, page_size[0], page_size[1]]),
            'Kids':Array(), 'Count':0,
        })

    def add_page(self, pageref):
        self['Kids'].append(pageref)
        self['Count'] += 1

    def get_ref(self, num):
        return self['Kids'][num-1]

class HashingStream(object):

    def __init__(self, f):
        self.f = f
        self.tell = f.tell
        self.hashobj = hashlib.sha256()
        self.last_char = b''

    def write(self, raw):
        self.write_raw(raw if isinstance(raw, bytes) else raw.encode('ascii'))

    def write_raw(self, raw):
        self.f.write(raw)
        self.hashobj.update(raw)
        if raw:
            self.last_char = raw[-1]

class Image(Stream):

    def __init__(self, data, w, h, depth, mask, soft_mask, dct):
        Stream.__init__(self)
        self.width, self.height, self.depth = w, h, depth
        self.mask, self.soft_mask = mask, soft_mask
        if dct:
            self.filters.append(Name('DCTDecode'))
        else:
            self.compress = True
        self.write(data)

    def add_extra_keys(self, d):
        d['Type'] = Name('XObject')
        d['Subtype']=  Name('Image')
        d['Width'] = self.width
        d['Height'] = self.height
        if self.depth == 1:
            d['ImageMask'] = True
            d['Decode'] = Array([1, 0])
        else:
            d['BitsPerComponent'] = 8
            d['ColorSpace'] = Name('Device' + ('RGB' if self.depth == 32 else
                                               'Gray'))
        if self.mask is not None:
            d['Mask'] = self.mask
        if self.soft_mask is not None:
            d['SMask'] = self.soft_mask

class PDFStream(object):

    PATH_OPS = {
        # stroke fill   fill-rule
        ( False, False, 'winding')  : 'n',
        ( False, False, 'evenodd')  : 'n',
        ( False, True,  'winding')  : 'f',
        ( False, True,  'evenodd')  : 'f*',
        ( True,  False, 'winding')  : 'S',
        ( True,  False, 'evenodd')  : 'S',
        ( True,  True,  'winding')  : 'B',
        ( True,  True,  'evenodd')  : 'B*',
    }

    def __init__(self, stream, page_size, compress=False, mark_links=False,
                 debug=print):
        self.stream = HashingStream(stream)
        self.compress = compress
        self.write_line(PDFVER)
        self.write_line(b'%íì¦"')
        creator = ('%s %s [http://calibre-ebook.com]'%(__appname__,
                                    __version__))
        self.write_line('%% Created by %s'%creator)
        self.objects = IndirectObjects()
        self.objects.add(PageTree(page_size))
        self.objects.add(Catalog(self.page_tree))
        self.current_page = Page(self.page_tree, compress=self.compress)
        self.info = Dictionary({
            'Creator':String(creator),
            'Producer':String(creator),
            'CreationDate': utcnow(),
                                })
        self.stroke_opacities, self.fill_opacities = {}, {}
        self.font_manager = FontManager(self.objects, self.compress)
        self.image_cache = {}
        self.pattern_cache, self.shader_cache = {}, {}
        self.debug = debug
        self.links = Links(self, mark_links, page_size)
        i = QImage(1, 1, QImage.Format_ARGB32)
        i.fill(qRgba(0, 0, 0, 255))
        self.alpha_bit = i.constBits().asstring(4).find(b'\xff')

    @property
    def page_tree(self):
        return self.objects[0]

    @property
    def catalog(self):
        return self.objects[1]

    def get_pageref(self, pagenum):
        return self.page_tree.obj.get_ref(pagenum)

    def set_metadata(self, title=None, author=None, tags=None):
        if title:
            self.info['Title'] = String(title)
        if author:
            self.info['Author'] = String(author)
        if tags:
            self.info['Keywords'] = String(tags)

    def write_line(self, byts=b''):
        byts = byts if isinstance(byts, bytes) else byts.encode('ascii')
        self.stream.write(byts + EOL)

    def transform(self, *args):
        if len(args) == 1:
            m = args[0]
            vals = [m.m11(), m.m12(), m.m21(), m.m22(), m.dx(), m.dy()]
        else:
            vals = args
        cm = ' '.join(map(fmtnum, vals))
        self.current_page.write_line(cm + ' cm')

    def save_stack(self):
        self.current_page.write_line('q')

    def restore_stack(self):
        self.current_page.write_line('Q')

    def reset_stack(self):
        self.current_page.write_line('Q q')

    def draw_rect(self, x, y, width, height, stroke=True, fill=False):
        self.current_page.write('%s re '%' '.join(map(fmtnum, (x, y, width, height))))
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, 'winding')])

    def write_path(self, path):
        for i, op in enumerate(path.ops):
            if i != 0:
                self.current_page.write_line()
            for x in op:
                self.current_page.write(
                (fmtnum(x) if isinstance(x, (int, long, float)) else x) + ' ')

    def draw_path(self, path, stroke=True, fill=False, fill_rule='winding'):
        if not path.ops: return
        self.write_path(path)
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, fill_rule)])

    def add_clip(self, path, fill_rule='winding'):
        if not path.ops: return
        self.write_path(path)
        op = 'W' if fill_rule == 'winding' else 'W*'
        self.current_page.write_line(op + ' ' + 'n')

    def serialize(self, o):
        serialize(o, self.current_page)

    def set_stroke_opacity(self, opacity):
        if opacity not in self.stroke_opacities:
            op = Dictionary({'Type':Name('ExtGState'), 'CA': opacity})
            self.stroke_opacities[opacity] = self.objects.add(op)
        self.current_page.set_opacity(self.stroke_opacities[opacity])

    def set_fill_opacity(self, opacity):
        opacity = float(opacity)
        if opacity not in self.fill_opacities:
            op = Dictionary({'Type':Name('ExtGState'), 'ca': opacity})
            self.fill_opacities[opacity] = self.objects.add(op)
        self.current_page.set_opacity(self.fill_opacities[opacity])

    def end_page(self):
        pageref = self.current_page.end(self.objects, self.stream)
        self.page_tree.obj.add_page(pageref)
        self.current_page = Page(self.page_tree, compress=self.compress)

    def draw_glyph_run(self, transform, size, font_metrics, glyphs):
        glyph_ids = {x[-1] for x in glyphs}
        fontref = self.font_manager.add_font(font_metrics, glyph_ids)
        name = self.current_page.add_font(fontref)
        self.current_page.write(b'BT ')
        serialize(Name(name), self.current_page)
        self.current_page.write(' %s Tf '%fmtnum(size))
        self.current_page.write('%s Tm '%' '.join(map(fmtnum, transform)))
        for x, y, glyph_id in glyphs:
            self.current_page.write_raw(('%s %s Td <%04X> Tj '%(
                fmtnum(x), fmtnum(y), glyph_id)).encode('ascii'))
        self.current_page.write_line(b' ET')

    def get_image(self, cache_key):
        return self.image_cache.get(cache_key, None)

    def write_image(self, data, w, h, depth, dct=False, mask=None,
                    soft_mask=None, cache_key=None):
        imgobj = Image(data, w, h, depth, mask, soft_mask, dct)
        self.image_cache[cache_key] = r = self.objects.add(imgobj)
        self.objects.commit(r, self.stream)
        return r

    def add_image(self, img, cache_key):
        ref = self.get_image(cache_key)
        if ref is not None:
            return ref

        fmt = img.format()
        image = QImage(img)
        if (image.depth() == 1 and img.colorTable().size() == 2 and
            img.colorTable().at(0) == QColor(Qt.black).rgba() and
            img.colorTable().at(1) == QColor(Qt.white).rgba()):
            if fmt == QImage.Format_MonoLSB:
                image = image.convertToFormat(QImage.Format_Mono)
            fmt = QImage.Format_Mono
        else:
            if (fmt != QImage.Format_RGB32 and fmt != QImage.Format_ARGB32):
                image = image.convertToFormat(QImage.Format_ARGB32)
                fmt = QImage.Format_ARGB32

        w = image.width()
        h = image.height()
        d = image.depth()

        if fmt == QImage.Format_Mono:
            bytes_per_line = (w + 7) >> 3
            data = image.constBits().asstring(bytes_per_line * h)
            return self.write_image(data, w, h, d, cache_key=cache_key)

        ba = QByteArray()
        buf = QBuffer(ba)
        image.save(buf, 'jpeg', 94)
        data = bytes(ba.data())
        has_alpha = has_mask = False
        soft_mask = mask = None

        if fmt == QImage.Format_ARGB32:
            tmask = image.constBits().asstring(4*w*h)[self.alpha_bit::4]
            sdata = bytearray(tmask)
            vals = set(sdata)
            vals.discard(255)
            has_mask = bool(vals)
            vals.discard(0)
            has_alpha = bool(vals)

        if has_alpha:
            soft_mask = self.write_image(tmask, w, h, 8)
        elif has_mask:
            # dither the soft mask to 1bit and add it. This also helps PDF
            # viewers without transparency support
            bytes_per_line = (w + 7) >> 3
            mdata = bytearray(0 for i in xrange(bytes_per_line * h))
            spos = mpos = 0
            for y in xrange(h):
                for x in xrange(w):
                    if sdata[spos]:
                        mdata[mpos + x>>3] |= (0x80 >> (x&7))
                    spos += 1
                mpos += bytes_per_line
            mdata = bytes(mdata)
            mask = self.write_image(mdata, w, h, 1)

        return self.write_image(data, w, h, 32, mask=mask, dct=True,
                                    soft_mask=soft_mask, cache_key=cache_key)

    def add_pattern(self, pattern):
        if pattern.cache_key not in self.pattern_cache:
            self.pattern_cache[pattern.cache_key] = self.objects.add(pattern)
        return self.current_page.add_pattern(self.pattern_cache[pattern.cache_key])

    def add_shader(self, shader):
        if shader.cache_key not in self.shader_cache:
            self.shader_cache[shader.cache_key] = self.objects.add(shader)
        return self.shader_cache[shader.cache_key]

    def draw_image(self, x, y, width, height, imgref):
        name = self.current_page.add_image(imgref)
        self.current_page.write('q %s 0 0 %s %s %s cm '%(fmtnum(width),
                            fmtnum(-height), fmtnum(x), fmtnum(y+height)))
        serialize(Name(name), self.current_page)
        self.current_page.write_line(' Do Q')

    def apply_color_space(self, color, pattern, stroke=False):
        wl = self.current_page.write_line
        if color is not None and pattern is None:
            wl(' '.join(map(fmtnum, color)) + (' RG' if stroke else ' rg'))
        elif color is None and pattern is not None:
            wl('/Pattern %s /%s %s'%('CS' if stroke else 'cs', pattern,
                                     'SCN' if stroke else 'scn'))
        elif color is not None and pattern is not None:
            col = ' '.join(map(fmtnum, color))
            wl('/PCSp %s %s /%s %s'%('CS' if stroke else 'cs', col, pattern,
                                     'SCN' if stroke else 'scn'))

    def apply_fill(self, color=None, pattern=None, opacity=None):
        if opacity is not None:
            self.set_fill_opacity(opacity)
        self.apply_color_space(color, pattern)

    def apply_stroke(self, color=None, pattern=None, opacity=None):
        if opacity is not None:
            self.set_stroke_opacity(opacity)
        self.apply_color_space(color, pattern, stroke=True)

    def end(self):
        if self.current_page.getvalue():
            self.end_page()
        self.font_manager.embed_fonts(self.debug)
        inforef = self.objects.add(self.info)
        self.links.add_links()
        self.objects.pdf_serialize(self.stream)
        self.write_line()
        startxref = self.objects.write_xref(self.stream)
        file_id = String(self.stream.hashobj.hexdigest().decode('ascii'))
        self.write_line('trailer')
        trailer = Dictionary({'Root':self.catalog, 'Size':len(self.objects)+1,
                              'ID':Array([file_id, file_id]), 'Info':inforef})
        serialize(trailer, self.stream)
        self.write_line('startxref')
        self.write_line('%d'%startxref)
        self.stream.write('%%EOF')

