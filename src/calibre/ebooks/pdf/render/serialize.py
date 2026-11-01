#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid at kovidgoyal.net>

import hashlib
import numbers
from typing import IO, TYPE_CHECKING, Protocol, cast

from qt.core import QBuffer, QByteArray, QColor, QImage, QPainter, Qt, QTransform, qRgba

from calibre.constants import __appname__, __version__
from calibre.ebooks.pdf.render.common import EOL, Array, Dictionary, Name, Reference, Stream, String, fmtnum, serialize
from calibre.ebooks.pdf.render.fonts import FontManager
from calibre.ebooks.pdf.render.links import Links
from calibre.utils.date import utcnow
from polyglot.builtins import as_unicode

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Sequence

    from calibre.ebooks.metadata.book.base import Metadata as BookMetadata
    from calibre.ebooks.pdf.render.fonts import GlyphMappedFontMetrics

PDFVER = b'%PDF-1.4'  # 1.4 is needed for XMP metadata


class CachedPDFObject(Protocol):
    @property
    def cache_key(self) -> Hashable: ...


class IndirectObjects:
    def __init__(self) -> None:
        self._list: list[object] = []
        self._map: dict[int, Reference[object]] = {}
        self._offsets: list[int | None] = []

    def __len__(self) -> int:
        return len(self._list)

    def add[T](self, o: T) -> Reference[T]:
        self._list.append(o)
        ref = Reference(len(self._list), o)
        self._map[id(o)] = ref
        self._offsets.append(None)
        return ref

    def commit(self, ref: Reference[object], stream: HashingStream) -> None:
        self.write_obj(stream, ref.num, ref.obj)

    def write_obj(self, stream: HashingStream, num: int, obj: object) -> None:
        stream.write(EOL)
        self._offsets[num - 1] = stream.tell()
        stream.write(f'{num} 0 obj')
        stream.write(EOL)
        serialize(obj, stream)
        if stream.last_char != EOL:
            stream.write(EOL)
        stream.write('endobj')
        stream.write(EOL)

    def __getitem__(self, o: object) -> Reference[object]:
        try:
            return self._map[id(self._list[o] if isinstance(o, numbers.Integral) else o)]
        except KeyError, IndexError:
            raise KeyError(f'The object {o!r} was not found')

    def pdf_serialize(self, stream: HashingStream) -> None:
        for i, obj in enumerate(self._list):
            offset = self._offsets[i]
            if offset is None:
                self.write_obj(stream, i + 1, obj)

    def write_xref(self, stream: HashingStream) -> int:
        self.xref_offset = stream.tell()
        stream.write(b'xref' + EOL)
        stream.write(f'0 {1 + len(self._offsets)}')
        stream.write(EOL)
        stream.write(f'{0:010} 65535 f ')
        stream.write(EOL)

        for offset in self._offsets:
            line = f'{offset:010} 00000 n '
            stream.write(line.encode('ascii') + EOL)
        return self.xref_offset


class Page(Stream):
    def __init__(self, parentref: Reference[PageTree], *args: bool, **kwargs: bool) -> None:
        super().__init__(*args, **kwargs)
        self.page_dict = Dictionary({
            'Type': Name('Page'),
            'Parent': parentref,
        })
        self.opacities: dict[Reference[Dictionary], str] = {}
        self.fonts: dict[Reference[Dictionary], str] = {}
        self.xobjects: dict[Reference[Image], str] = {}
        self.patterns: dict[Reference[CachedPDFObject], str] = {}

    def set_opacity(self, opref: Reference[Dictionary]) -> None:
        if opref not in self.opacities:
            self.opacities[opref] = f'Opa{len(self.opacities)}'
        name = self.opacities[opref]
        serialize(Name(name), self)
        self.write(b' gs ')

    def add_font(self, fontref: Reference[Dictionary]) -> str:
        if fontref not in self.fonts:
            self.fonts[fontref] = f'F{len(self.fonts)}'
        return self.fonts[fontref]

    def add_image(self, imgref: Reference[Image]) -> str:
        if imgref not in self.xobjects:
            self.xobjects[imgref] = f'Image{len(self.xobjects)}'
        return self.xobjects[imgref]

    def add_pattern(self, patternref: Reference[CachedPDFObject]) -> str:
        if patternref not in self.patterns:
            self.patterns[patternref] = f'Pat{len(self.patterns)}'
        return self.patterns[patternref]

    def add_resources(self) -> None:
        r = Dictionary()
        if self.opacities:
            extgs = Dictionary()
            for opref, name in self.opacities.items():
                extgs[name] = opref
            r['ExtGState'] = extgs
        if self.fonts:
            fonts = Dictionary()
            for ref, name in self.fonts.items():
                fonts[name] = ref
            r['Font'] = fonts
        if self.xobjects:
            xobjects = Dictionary()
            for ref, name in self.xobjects.items():
                xobjects[name] = ref
            r['XObject'] = xobjects
        if self.patterns:
            r['ColorSpace'] = Dictionary({'PCSp': Array([Name('Pattern'), Name('DeviceRGB')])})
            patterns = Dictionary()
            for ref, name in self.patterns.items():
                patterns[name] = ref
            r['Pattern'] = patterns
        if r:
            self.page_dict['Resources'] = r

    def end(self, objects: IndirectObjects, stream: HashingStream) -> Reference[Dictionary]:
        contents = objects.add(self)
        objects.commit(contents, stream)
        self.page_dict['Contents'] = contents
        self.add_resources()
        ret = objects.add(self.page_dict)
        # objects.commit(ret, stream)
        return ret


class Path:
    def __init__(self) -> None:
        self.ops: list[tuple[float | str, ...]] = []

    def move_to(self, x: float, y: float) -> None:
        self.ops.append((x, y, 'm'))

    def line_to(self, x: float, y: float) -> None:
        self.ops.append((x, y, 'l'))

    def curve_to(self, x1: float, y1: float, x2: float, y2: float, x: float, y: float) -> None:
        self.ops.append((x1, y1, x2, y2, x, y, 'c'))

    def close(self) -> None:
        self.ops.append(('h',))


class Catalog(Dictionary):
    def __init__(self, pagetree: Reference[PageTree]) -> None:
        super().__init__({'Type': Name('Catalog'), 'Pages': pagetree})


class PageTree(Dictionary):
    def __init__(self, page_size: tuple[float, float]) -> None:
        super().__init__({
            'Type': Name('Pages'),
            'MediaBox': Array([0, 0, page_size[0], page_size[1]]),
            'Kids': Array(),
            'Count': 0,
        })

    def add_page(self, pageref: Reference[Dictionary]) -> None:
        self['Kids'].append(pageref)
        self['Count'] += 1

    def get_ref(self, num: int) -> Reference[Dictionary]:
        return self['Kids'][num - 1]

    def get_num(self, pageref: Reference[Dictionary]) -> int:
        try:
            return self['Kids'].index(pageref) + 1
        except ValueError:
            return -1


class HashingStream:
    def __init__(self, f: IO[bytes]) -> None:
        self.f = f
        self.tell = f.tell
        self.hashobj = hashlib.sha256()
        self.last_char = b''

    def write(self, raw: bytes | str) -> None:
        self.write_raw(raw if isinstance(raw, bytes) else raw.encode('ascii'))

    def write_raw(self, raw: bytes) -> None:
        self.f.write(raw)
        self.hashobj.update(raw)
        if raw:
            self.last_char = raw[-1:]


class Image(Stream):
    def __init__(self, data: bytes, w: int, h: int, depth: int, mask: Reference[Image] | None, soft_mask: Reference[Image] | None, dct: bool) -> None:
        Stream.__init__(self)
        self.width, self.height, self.depth = w, h, depth
        self.mask, self.soft_mask = mask, soft_mask
        if dct:
            self.filters.append(Name('DCTDecode'))
        else:
            self.compress = True
        self.write(data)

    def add_extra_keys(self, d: Dictionary) -> None:
        d['Type'] = Name('XObject')
        d['Subtype'] = Name('Image')
        d['Width'] = self.width
        d['Height'] = self.height
        if self.depth == 1:
            d['ImageMask'] = True
            d['Decode'] = Array([1, 0])
        else:
            d['BitsPerComponent'] = 8
            d['ColorSpace'] = Name('Device' + ('RGB' if self.depth == 32 else 'Gray'))
        if self.mask is not None:
            d['Mask'] = self.mask
        if self.soft_mask is not None:
            d['SMask'] = self.soft_mask


class Metadata(Stream):
    def __init__(self, mi: BookMetadata) -> None:
        Stream.__init__(self)
        from calibre.ebooks.metadata.xmp import metadata_to_xmp_packet

        self.write(metadata_to_xmp_packet(mi))

    def add_extra_keys(self, d: Dictionary) -> None:
        d['Type'] = Name('Metadata')
        d['Subtype'] = Name('XML')


class PDFStream:
    PATH_OPS = {
        # stroke fill   fill-rule
        (False, False, 'winding'): 'n',
        (False, False, 'evenodd'): 'n',
        (False, True, 'winding'): 'f',
        (False, True, 'evenodd'): 'f*',
        (True, False, 'winding'): 'S',
        (True, False, 'evenodd'): 'S',
        (True, True, 'winding'): 'B',
        (True, True, 'evenodd'): 'B*',
    }

    def __init__(
        self,
        stream: IO[bytes],
        page_size: tuple[float, float],
        compress: bool = False,
        mark_links: bool = False,
        debug: Callable[[str], object] = print,
    ) -> None:
        self.stream = HashingStream(stream)
        self.compress = compress
        self.write_line(PDFVER)
        self.write_line('%íì¦"'.encode())
        creator = f'{__appname__} {__version__} [https://calibre-ebook.com]'
        self.write_line(f'% Created by {creator}')
        self.objects = IndirectObjects()
        self.objects.add(PageTree(page_size))
        self.objects.add(Catalog(self.page_tree))
        self.current_page = Page(self.page_tree, compress=self.compress)
        self.info = Dictionary({
            'Creator': String(creator),
            'Producer': String(creator),
            'CreationDate': utcnow(),
        })
        self.stroke_opacities: dict[float, Reference[Dictionary]] = {}
        self.fill_opacities: dict[float, Reference[Dictionary]] = {}
        self.font_manager = FontManager(self.objects, self.compress)
        self.image_cache: dict[int | None, Reference[Image]] = {}
        self.pattern_cache: dict[Hashable, Reference[CachedPDFObject]] = {}
        self.shader_cache: dict[Hashable, Reference[CachedPDFObject]] = {}
        self.debug = debug
        self.page_size = page_size
        self.links = Links(self, mark_links, page_size)
        i = QImage(1, 1, QImage.Format.Format_ARGB32)
        i.fill(qRgba(0, 0, 0, 255))
        i_bits = i.constBits()
        assert i_bits is not None
        self.alpha_bit = i_bits.asstring(4).find(b'\xff')
        self.bw_image_color_table = frozenset((
            QColor(Qt.GlobalColor.black).rgba(),
            QColor(Qt.GlobalColor.white).rgba(),
        ))

    @property
    def page_tree(self) -> Reference[PageTree]:
        # The PageTree is always the first object, added in __init__
        return cast('Reference[PageTree]', self.objects[0])

    @property
    def catalog(self) -> Reference[Catalog]:
        # The Catalog is always the second object, added in __init__
        return cast('Reference[Catalog]', self.objects[1])

    def get_pageref(self, pagenum: int) -> Reference[Dictionary]:
        return self.page_tree.obj.get_ref(pagenum)

    def set_metadata(self, title: str | None = None, author: str | None = None, tags: str | None = None, mi: BookMetadata | None = None) -> None:
        if title:
            self.info['Title'] = String(title)
        if author:
            self.info['Author'] = String(author)
        if tags:
            self.info['Keywords'] = String(tags)
        if mi is not None:
            self.metadata = self.objects.add(Metadata(mi))
            self.catalog.obj['Metadata'] = self.metadata

    def write_line(self, byts: bytes | str = b'') -> None:
        byts = byts if isinstance(byts, bytes) else byts.encode('ascii')
        self.stream.write(byts + EOL)

    def transform(self, *args: QTransform | float) -> None:
        vals: Sequence[QTransform | float]
        if len(args) == 1:
            # the single argument form is only used with a QTransform
            m = cast('QTransform', args[0])
            vals = [m.m11(), m.m12(), m.m21(), m.m22(), m.dx(), m.dy()]
        else:
            vals = args
        cm = ' '.join(map(fmtnum, vals))
        self.current_page.write_line(cm + ' cm')

    def save_stack(self) -> None:
        self.current_page.write_line('q')

    def restore_stack(self) -> None:
        self.current_page.write_line('Q')

    def reset_stack(self) -> None:
        self.current_page.write_line('Q q')

    def draw_rect(self, x: float, y: float, width: float, height: float, stroke: bool = True, fill: bool = False) -> None:
        self.current_page.write('{} re '.format(' '.join(map(fmtnum, (x, y, width, height)))))
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, 'winding')])

    def write_path(self, path: Path) -> None:
        for i, op in enumerate(path.ops):
            if i != 0:
                self.current_page.write_line()
            for x in op:
                self.current_page.write((x if isinstance(x, str) else fmtnum(x)) + ' ')

    def draw_path(self, path: Path, stroke: bool = True, fill: bool = False, fill_rule: str = 'winding') -> None:
        if not path.ops:
            return
        self.write_path(path)
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, fill_rule)])

    def add_clip(self, path: Path, fill_rule: str = 'winding') -> None:
        if not path.ops:
            return
        self.write_path(path)
        op = 'W' if fill_rule == 'winding' else 'W*'
        self.current_page.write_line(op + ' ' + 'n')

    def serialize(self, o: object) -> None:
        serialize(o, self.current_page)

    def set_stroke_opacity(self, opacity: float) -> None:
        if opacity not in self.stroke_opacities:
            op = Dictionary({'Type': Name('ExtGState'), 'CA': opacity})
            self.stroke_opacities[opacity] = self.objects.add(op)
        self.current_page.set_opacity(self.stroke_opacities[opacity])

    def set_fill_opacity(self, opacity: float) -> None:
        opacity = float(opacity)
        if opacity not in self.fill_opacities:
            op = Dictionary({'Type': Name('ExtGState'), 'ca': opacity})
            self.fill_opacities[opacity] = self.objects.add(op)
        self.current_page.set_opacity(self.fill_opacities[opacity])

    def end_page(self, drop_page: bool = False) -> None:
        if not drop_page:
            pageref = self.current_page.end(self.objects, self.stream)
            self.page_tree.obj.add_page(pageref)
        self.current_page = Page(self.page_tree, compress=self.compress)

    def draw_glyph_run(self, transform: Sequence[float], size: float, font_metrics: GlyphMappedFontMetrics, glyphs: Sequence[tuple[float, float, int]]) -> None:
        glyph_ids = {x[-1] for x in glyphs}
        fontref = self.font_manager.add_font(font_metrics, glyph_ids)
        name = self.current_page.add_font(fontref)
        self.current_page.write(b'BT ')
        serialize(Name(name), self.current_page)
        self.current_page.write(f' {fmtnum(size)} Tf ')
        self.current_page.write('{} Tm '.format(' '.join(map(fmtnum, transform))))
        for x, y, glyph_id in glyphs:
            self.current_page.write_raw((f'{fmtnum(x)} {fmtnum(y)} Td <{glyph_id:04X}> Tj ').encode('ascii'))
        self.current_page.write_line(b' ET')

    def get_image(self, cache_key: int | None) -> Reference[Image] | None:
        return self.image_cache.get(cache_key, None)

    def write_image(
        self,
        data: bytes,
        w: int,
        h: int,
        depth: int,
        dct: bool = False,
        mask: Reference[Image] | None = None,
        soft_mask: Reference[Image] | None = None,
        cache_key: int | None = None,
    ) -> Reference[Image]:
        imgobj = Image(data, w, h, depth, mask, soft_mask, dct)
        self.image_cache[cache_key] = r = self.objects.add(imgobj)
        self.objects.commit(r, self.stream)
        return r

    def add_jpeg_image(self, img_data: bytes, w: int, h: int, cache_key: int | None = None, depth: int = 32) -> Reference[Image]:
        if cache_key is not None:
            ref = self.get_image(cache_key)
            if ref is not None:
                return ref
        return self.write_image(img_data, w, h, depth, dct=True, cache_key=cache_key)

    def add_image(self, img: QImage, cache_key: int) -> Reference[Image]:
        ref = self.get_image(cache_key)
        if ref is not None:
            return ref

        fmt = img.format()
        image = QImage(img)
        if image.depth() == 1 and frozenset(img.colorTable()) == self.bw_image_color_table:
            if fmt == QImage.Format.Format_MonoLSB:
                image = image.convertToFormat(QImage.Format.Format_Mono)
            fmt = QImage.Format.Format_Mono
        elif fmt not in (QImage.Format.Format_RGB32, QImage.Format.Format_ARGB32):
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            fmt = QImage.Format.Format_ARGB32

        w = image.width()
        h = image.height()
        d = image.depth()

        if fmt == QImage.Format.Format_Mono:
            bytes_per_line = (w + 7) >> 3
            mono_bits = image.constBits()
            assert mono_bits is not None
            data = mono_bits.asstring(bytes_per_line * h)
            return self.write_image(data, w, h, d, cache_key=cache_key)

        has_alpha = False
        soft_mask = None

        if fmt == QImage.Format.Format_ARGB32:
            argb_bits = image.constBits()
            assert argb_bits is not None
            tmask = argb_bits.asstring(4 * w * h)[self.alpha_bit :: 4]
            sdata = bytearray(tmask)
            vals = set(sdata)
            vals.discard(255)  # discard opaque pixels
            has_alpha = bool(vals)
            if has_alpha:
                # Blend image onto a white background as otherwise Qt will render
                # transparent pixels as black
                background = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
                background.fill(Qt.GlobalColor.white)
                painter = QPainter(background)
                painter.drawImage(0, 0, image)
                painter.end()
                image = background

        ba = QByteArray()
        buf = QBuffer(ba)
        image.save(buf, 'jpeg', 94)
        data = ba.data()

        if has_alpha:
            soft_mask = self.write_image(tmask, w, h, 8)

        return self.write_image(data, w, h, 32, dct=True, soft_mask=soft_mask, cache_key=cache_key)

    def add_pattern(self, pattern: CachedPDFObject) -> str:
        if pattern.cache_key not in self.pattern_cache:
            self.pattern_cache[pattern.cache_key] = self.objects.add(pattern)
        return self.current_page.add_pattern(self.pattern_cache[pattern.cache_key])

    def add_shader(self, shader: CachedPDFObject) -> Reference[CachedPDFObject]:
        if shader.cache_key not in self.shader_cache:
            self.shader_cache[shader.cache_key] = self.objects.add(shader)
        return self.shader_cache[shader.cache_key]

    def draw_image(self, x: float, y: float, width: float, height: float, imgref: Reference[Image]) -> None:
        self.draw_image_with_transform(imgref, scaling=(width, -height), translation=(x, y + height))

    def draw_image_with_transform(self, imgref: Reference[Image], translation: Sequence[float] = (0, 0), scaling: Sequence[float] = (1, 1)) -> None:
        name = self.current_page.add_image(imgref)
        self.current_page.write('q {} 0 0 {} {} {} cm '.format(*(tuple(scaling) + tuple(translation))))
        serialize(Name(name), self.current_page)
        self.current_page.write_line(' Do Q')

    def apply_color_space(self, color: Sequence[float] | None, pattern: str | None, stroke: bool = False) -> None:
        wl = self.current_page.write_line
        if color is not None and pattern is None:
            wl(' '.join(map(fmtnum, color)) + (' RG' if stroke else ' rg'))
        elif color is None and pattern is not None:
            wl('/Pattern {} /{} {}'.format('CS' if stroke else 'cs', pattern, 'SCN' if stroke else 'scn'))
        elif color is not None and pattern is not None:
            col = ' '.join(map(fmtnum, color))
            wl('/PCSp {} {} /{} {}'.format('CS' if stroke else 'cs', col, pattern, 'SCN' if stroke else 'scn'))

    def apply_fill(self, color: Sequence[float] | None = None, pattern: str | None = None, opacity: float | None = None) -> None:
        if opacity is not None:
            self.set_fill_opacity(opacity)
        self.apply_color_space(color, pattern)

    def apply_stroke(self, color: Sequence[float] | None = None, pattern: str | None = None, opacity: float | None = None) -> None:
        if opacity is not None:
            self.set_stroke_opacity(opacity)
        self.apply_color_space(color, pattern, stroke=True)

    def end(self) -> None:
        if self.current_page.getvalue():
            self.end_page()
        self.font_manager.embed_fonts(self.debug)
        inforef = self.objects.add(self.info)
        self.links.add_links()
        self.objects.pdf_serialize(self.stream)
        self.write_line()
        startxref = self.objects.write_xref(self.stream)
        file_id = String(as_unicode(self.stream.hashobj.hexdigest()))
        self.write_line('trailer')
        trailer = Dictionary({
            'Root': self.catalog,
            'Size': len(self.objects) + 1,
            'ID': Array([file_id, file_id]),
            'Info': inforef,
        })
        serialize(trailer, self.stream)
        self.write_line('startxref')
        self.write_line(f'{startxref}')
        self.stream.write('%%EOF')
