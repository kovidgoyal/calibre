# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

import array
import collections
import io
import re
import struct
from compression import zlib
from typing import IO, TYPE_CHECKING, ClassVar, cast

from calibre import prepare_string_for_xml
from calibre.ebooks.html_entities import entity_to_unicode_in_python
from calibre.ebooks.lrf import PRS500_PROFILE, LRFParseError
from calibre.ebooks.lrf.tags import Tag

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

    from calibre.ebooks.lrf.lrfparser import LRFDocument

ruby_tags = {
    0xF575: ['rubyAlignAndAdjust', 'W'],
    0xF576: ['rubyoverhang', 'W', {0: 'none', 1: 'auto'}],
    0xF577: ['empdotsposition', 'W', {1: 'before', 2: 'after'}],
    0xF578: ['', 'parse_empdots'],
    0xF579: ['emplineposition', 'W', {1: 'before', 2: 'after'}],
    0xF57A: ['emplinetype', 'W', {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}],
}


class LRFObject:
    tag_map: ClassVar[dict] = {
        0xF500: ['', ''],
        0xF502: ['infoLink', 'D'],
        0xF501: ['', ''],
    }

    @classmethod
    def descramble_buffer(cls, buf: bytes, l: int, xorKey: int) -> bytes:
        i = 0
        a = array.array('B', buf)
        while l > 0:
            a[i] ^= xorKey
            i += 1
            l -= 1
        return a.tobytes()

    @classmethod
    def parse_empdots(self, tag: Tag, f: IO[bytes]) -> None:
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.contents

    @staticmethod
    def tag_to_val(h: Sequence[object], obj: LRFObject | None, tag: Tag, stream: IO[bytes] | None) -> object:
        val = None
        if h[1] == 'D':
            val = tag.dword
        elif h[1] == 'W':
            val = tag.word
        elif h[1] == 'w':
            val = tag.word
            if val > 0x8000:
                val -= 0x10000
        elif h[1] == 'B':
            val = tag.byte
        elif h[1] == 'P':
            val = tag.contents
        elif h[1] != '':
            val = getattr(obj, cast('str', h[1]))(tag, stream)
        if len(h) > 2:
            # a mapping of values or a converter like Color
            conv = cast('Mapping[object, object] | Callable[[object], object]', h[2])
            val = conv(val) if callable(conv) else conv[val]
        return val

    def __init__(self, document: LRFDocument | None, stream: IO[bytes], id: int, scramble_key: int, boundary: int) -> None:
        self._scramble_key = scramble_key
        # document is None only when meta.get_cover() reads Image and ImageStream objects
        self._document = cast('LRFDocument', document)
        self.id = id

        while stream.tell() < boundary:
            tag = Tag(stream)
            self.handle_tag(tag, stream)

    def parse_bg_image(self, tag: Tag, f: IO[bytes]) -> None:
        self.bg_image_mode, self.bg_image_id = struct.unpack('<HI', tag.contents)

    def handle_tag(self, tag: Tag, stream: IO[bytes], tag_map: Mapping[int, Sequence[object]] | None = None) -> None:
        if tag_map is None:
            tag_map = self.__class__.tag_map
        if tag.id in tag_map:
            h = tag_map[tag.id]
            val = LRFObject.tag_to_val(h, self, tag, stream)
            if h[1] != '' and h[0] != '':
                setattr(self, cast('str', h[0]), val)
        else:
            raise LRFParseError(f'Unknown tag in {self.__class__.__name__}: {tag}')

    def __iter__(self) -> Iterator[object]:
        yield from range(0)

    def __str__(self) -> str:
        return self.__class__.__name__


class LRFContentObject(LRFObject):
    tag_map = {}

    def __init__(self, byts: bytes | IO[bytes], objects: dict[int, LRFObject]) -> None:
        self.stream: IO[bytes] = byts if hasattr(byts, 'read') else io.BytesIO(byts)  # ty: ignore[invalid-assignment] hasattr() does not narrow to IO
        length = self.stream_size()
        self.objects = objects
        self._contents = []
        self.current = 0
        self.in_container = True
        self.parse_stream(length)

    def parse_stream(self, length: int) -> None:
        while self.in_container and self.stream.tell() < length:
            tag = Tag(self.stream)
            self.handle_tag(tag)

    def stream_size(self) -> int:
        pos = self.stream.tell()
        self.stream.seek(0, 2)
        size = self.stream.tell()
        self.stream.seek(pos)
        return size

    def handle_tag(self, tag: Tag, stream: IO[bytes] | None = None, tag_map: Mapping[int, Sequence[object]] | None = None) -> None:
        if tag.id in self.tag_map:
            action = self.tag_map[tag.id]
            if isinstance(action, str):
                func, args = action, ()
            else:
                func, args = action[0], (action[1],)
            getattr(self, func)(tag, *args)
        else:
            raise LRFParseError(f'Unknown tag in {self.__class__.__name__}: {tag}')

    def __iter__(self) -> Iterator[object]:
        yield from self._contents


class LRFStream(LRFObject):
    tag_map = {
        0xF504: ['', 'read_stream_size'],
        0xF554: ['stream_flags', 'W'],
        0xF505: ['', 'read_stream'],
        0xF506: ['', 'end_stream'],
    }
    tag_map.update(LRFObject.tag_map)
    stream_flags: int  # set via tag_map[0xF554]
    stream: str | bytes | None

    def __init__(self, document: LRFDocument | None, stream: IO[bytes], id: int, scramble_key: int, boundary: int) -> None:
        self.stream = ''
        self.stream_size = 0
        self.stream_read = False
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)

    def read_stream_size(self, tag: Tag, stream: IO[bytes]) -> None:
        self.stream_size = tag.dword

    def end_stream(self, tag: Tag | None, stream: IO[bytes] | None) -> None:
        self.stream_read = True

    def read_stream(self, tag: Tag, stream: IO[bytes]) -> None:
        if self.stream_read:
            raise LRFParseError('There can be only one stream per object')
        if not hasattr(self, 'stream_flags'):
            raise LRFParseError('Stream flags not initialized')
        self.stream = stream.read(self.stream_size)
        if self.stream_flags & 0x200 != 0:
            l = len(self.stream)
            key = self._scramble_key & 0xFF
            if key != 0 and key <= 0xF0:
                key = l % key + 0xF
            else:
                key = 0
            if l > 0x400 and (isinstance(self, (ImageStream, Font, SoundStream))):
                l = 0x400
            self.stream = self.descramble_buffer(self.stream, l, key)
        if self.stream_flags & 0x100 != 0:
            decomp_size = struct.unpack('<I', self.stream[:4])[0]
            self.stream = zlib.decompress(self.stream[4:])
            if len(self.stream) != decomp_size:
                raise LRFParseError('Stream decompressed size is wrong!')
        if stream.read(2) != b'\x06\xf5':
            print(f'Warning: corrupted end-of-stream tag at {stream.tell() - 2:08X}; skipping it')
        self.end_stream(None, None)


class PageTree(LRFObject):
    tag_map = {
        0xF55C: ['_contents', 'P'],
    }
    tag_map.update(LRFObject.tag_map)

    def __iter__(self) -> Iterator[LRFObject]:
        for id in getattr(self, '_contents', []):
            yield self._document.objects[id]


class StyleObject:
    tag_map: ClassVar[dict]
    id: int

    def _tags_to_xml(self) -> str:
        s = ''
        for h in self.tag_map.values():
            attr = h[0]
            if isinstance(attr, str) and hasattr(self, attr):
                s += f'{attr}="{getattr(self, attr)}" '
        return s

    def __str__(self) -> str:
        s = '<{} objid="{}" stylelabel="{}" '.format(self.__class__.__name__.replace('Attr', 'Style'), self.id, self.id)
        s += self._tags_to_xml()
        s += '/>\n'
        return s

    def as_dict(self) -> dict[str, object]:
        d: dict[str, object] = {}
        for h in self.tag_map.values():
            attr = h[0]
            if isinstance(attr, str) and hasattr(self, attr):
                d[attr] = getattr(self, attr)
        return d


class PageAttr(StyleObject, LRFObject):
    tag_map = {
        0xF507: ['oddheaderid', 'D'],
        0xF508: ['evenheaderid', 'D'],
        0xF509: ['oddfooterid', 'D'],
        0xF50A: ['evenfooterid', 'D'],
        0xF521: ['topmargin', 'W'],
        0xF522: ['headheight', 'W'],
        0xF523: ['headsep', 'W'],
        0xF524: ['oddsidemargin', 'W'],
        0xF52C: ['evensidemargin', 'W'],
        0xF525: ['textheight', 'W'],
        0xF526: ['textwidth', 'W'],
        0xF527: ['footspace', 'W'],
        0xF528: ['footheight', 'W'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF52B: ['pageposition', 'W', {0: 'any', 1: 'upper', 2: 'lower'}],
        0xF52A: ['setemptyview', 'W', {1: 'show', 0: 'empty'}],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xF529: ['', 'parse_bg_image'],
    }
    tag_map.update(LRFObject.tag_map)
    oddheaderid: int  # set via tag_map[0xF507]
    evenheaderid: int  # set via tag_map[0xF508]
    oddfooterid: int  # set via tag_map[0xF509]
    evenfooterid: int  # set via tag_map[0xF50A]

    @classmethod
    def to_css(cls, obj: object, inline: bool = False) -> str:
        return ''


class Color:
    def __init__(self, val: int) -> None:
        self.a, self.r, self.g, self.b = val & 0xFF, (val >> 8) & 0xFF, (val >> 16) & 0xFF, (val >> 24) & 0xFF

    def __str__(self) -> str:
        return f'0x{self.a:02x}{self.r:02x}{self.g:02x}{self.b:02x}'

    def __len__(self) -> int:
        return 4

    def __getitem__(self, i: int) -> int:  # Qt compatible ordering and values
        return (self.r, self.g, self.b, 0xFF - self.a)[i]  # In Qt 0xff is opaque while in LRS 0x00 is opaque

    def to_html(self) -> str:
        return f'rgb({self.r}, {self.g}, {self.b})'


class EmptyPageElement:
    def __iter__(self) -> Iterator[object]:
        yield from range(0)

    def __str__(self) -> str:
        return ''


class PageDiv(EmptyPageElement):
    def __init__(self, pain: int, spacesize: int, linewidth: int, linecolor: int) -> None:
        self.pain, self.spacesize, self.linewidth = pain, spacesize, linewidth
        self.linecolor = Color(linecolor)

    def __str__(self) -> str:
        return f'\n<PageDiv pain="{self.pain}" spacesize="{self.spacesize}" linewidth="{self.linewidth}" linecolor="{self.linecolor}" />\n'


class RuledLine(EmptyPageElement):
    linetype_map = {0x00: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted', 0x13: 'unknown13'}

    def __init__(self, linelength: int, linetype: int, linewidth: int, linecolor: int) -> None:
        self.linelength, self.linewidth = linelength, linewidth
        self.linetype = self.linetype_map[linetype]
        self.linecolor = Color(linecolor)
        self.id = -1

    def __str__(self) -> str:
        return f'\n<RuledLine linelength="{self.linelength}" linetype="{self.linetype}" linewidth="{self.linewidth}" linecolor="{self.linecolor}" />\n'


class Wait(EmptyPageElement):
    def __init__(self, time: int) -> None:
        self.time = time

    def __str__(self) -> str:
        return f'\n<Wait time="{self.time}" />\n'


class Locate(EmptyPageElement):
    pos_map = {1: 'bottomleft', 2: 'bottomright', 3: 'topright', 4: 'topleft', 5: 'base'}

    def __init__(self, pos: int) -> None:
        self.pos = self.pos_map[pos]

    def __str__(self) -> str:
        return f'\n<Locate pos="{self.pos}" />\n'


class BlockSpace(EmptyPageElement):
    def __init__(self, xspace: int, yspace: int) -> None:
        self.xspace, self.yspace = xspace, yspace

    def __str__(self) -> str:
        return f'\n<BlockSpace xspace="{self.xspace}" yspace="{self.yspace}" />\n'


class Page(LRFStream):
    tag_map = {
        0xF503: ['style_id', 'D'],
        0xF50B: ['obj_list', 'P'],
        0xF571: ['', ''],
        0xF57C: ['parent_page_tree', 'D'],
    }
    tag_map.update(PageAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    style_id: int  # set via tag_map[0xF503]
    style = property(fget=lambda self: self._document.objects[self.style_id])
    evenheader = property(fget=lambda self: self._document.objects[self.style.evenheaderid])
    evenfooter = property(fget=lambda self: self._document.objects[self.style.evenfooterid])
    oddheader = property(fget=lambda self: self._document.objects[self.style.oddheaderid])
    oddfooter = property(fget=lambda self: self._document.objects[self.style.oddfooterid])

    class Content(LRFContentObject):
        tag_map = {
            0xF503: 'link',
            0xF54E: 'page_div',
            0xF547: 'x_space',
            0xF546: 'y_space',
            0xF548: 'do_pos',
            0xF573: 'ruled_line',
            0xF5D4: 'wait',
            0xF5D6: 'sound_stop',
        }

        def __init__(self, byts: bytes | IO[bytes], objects: dict[int, LRFObject]) -> None:
            self.in_blockspace = False
            LRFContentObject.__init__(self, byts, objects)

        def link(self, tag: Tag) -> None:
            self.close_blockspace()
            self._contents.append(self.objects[tag.dword])

        def page_div(self, tag: Tag) -> None:
            self.close_blockspace()
            pars = struct.unpack('<HIHI', tag.contents)
            self._contents.append(PageDiv(*pars))

        def x_space(self, tag: Tag) -> None:
            self.xspace = tag.word
            self.in_blockspace = True

        def y_space(self, tag: Tag) -> None:
            self.yspace = tag.word
            self.in_blockspace = True

        def do_pos(self, tag: Tag) -> None:
            self.pos = tag.word  # mapped to a name by Locate
            self.in_blockspace = True

        def ruled_line(self, tag: Tag) -> None:
            self.close_blockspace()
            pars = struct.unpack('<HHHI', tag.contents)
            self._contents.append(RuledLine(*pars))

        def wait(self, tag: Tag) -> None:
            self.close_blockspace()
            self._contents.append(Wait(tag.word))

        def sound_stop(self, tag: Tag) -> None:
            self.close_blockspace()

        def close_blockspace(self) -> None:
            if self.in_blockspace:
                if hasattr(self, 'pos'):
                    self._contents.append(Locate(self.pos))
                    delattr(self, 'pos')
                else:
                    xspace = self.xspace if hasattr(self, 'xspace') else 0
                    yspace = self.yspace if hasattr(self, 'yspace') else 0
                    self._contents.append(BlockSpace(xspace, yspace))
                    if hasattr(self, 'xspace'):
                        delattr(self, 'xspace')
                    if hasattr(self, 'yspace'):
                        delattr(self, 'yspace')

    def header(self, odd: bool) -> LRFObject:
        style = cast('PageAttr', self._document.objects[self.style_id])
        id = style.oddheaderid if odd else style.evenheaderid
        return self._document.objects[id]

    def footer(self, odd: bool) -> LRFObject:
        style = cast('PageAttr', self._document.objects[self.style_id])
        id = style.oddfooterid if odd else style.evenfooterid
        return self._document.objects[id]

    def initialize(self) -> None:
        self.content = Page.Content(cast('bytes', self.stream), self._document.objects)  # pages always have a stream

    def __iter__(self) -> Iterator[object]:
        yield from self.content

    def __str__(self) -> str:
        s = f'\n<Page pagestyle="{self.style_id}" objid="{self.id}">\n'
        for i in self:
            s += str(i)
        s += '\n</Page>\n'
        return s

    def to_html(self) -> str:
        s = ''
        for i in self:
            s += i.to_html()  # ty: ignore[unresolved-attribute] pre-existing, only Block has to_html()
        return s


class BlockAttr(StyleObject, LRFObject):
    tag_map = {
        0xF531: ['blockwidth', 'W'],
        0xF532: ['blockheight', 'W'],
        0xF533: [
            'blockrule',
            'W',
            {
                0x14: 'horz-fixed',
                0x12: 'horz-adjustable',
                0x41: 'vert-fixed',
                0x21: 'vert-adjustable',
                0x44: 'block-fixed',
                0x22: 'block-adjustable',
            },
        ],
        0xF534: ['bgcolor', 'D', Color],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W'],
        0xF537: ['framecolor', 'D', Color],
        0xF52E: ['framemode', 'W', {0: 'none', 2: 'curve', 1: 'square'}],
        0xF538: ['topskip', 'W'],
        0xF539: ['sidemargin', 'W'],
        0xF53A: ['footskip', 'W'],
        0xF529: ['', 'parse_bg_image'],
    }
    tag_map.update(LRFObject.tag_map)
    bgcolor: Color  # set via tag_map[0xF534]
    framecolor: Color  # set via tag_map[0xF537]

    @classmethod
    def to_css(cls, obj: BlockAttr | Block, inline: bool = False) -> str:
        ans = ''

        def item(line: str) -> str:
            ans = '' if inline else '\t'
            ans += line
            ans += ' ' if inline else '\n'
            return ans

        if hasattr(obj, 'sidemargin'):
            margin = str(obj.sidemargin) + 'px'
            ans += item('margin-left: {m}; margin-right: {m};'.format(**dict(m=margin)))
        if hasattr(obj, 'topskip'):
            ans += item(f'margin-top: {obj.topskip}px;')
        if hasattr(obj, 'footskip'):
            ans += item(f'margin-bottom: {obj.footskip}px;')
        if hasattr(obj, 'framewidth'):
            ans += item(f'border: solid {obj.framewidth}px')
        if hasattr(obj, 'framecolor') and obj.framecolor.a < 255:
            ans += item(f'border-color: {obj.framecolor.to_html()};')
        if hasattr(obj, 'bgcolor') and obj.bgcolor.a < 255:
            ans += item(f'background-color: {obj.bgcolor.to_html()};')

        return ans


class TextCSS:
    FONT_MAP: ClassVar[collections.defaultdict[str, str]]

    @classmethod
    def to_css(cls, obj: object, inline: bool = False) -> str:
        ans = ''

        def item(line: str) -> str:
            ans = '' if inline else '\t'
            ans += line
            ans += ' ' if inline else '\n'
            return ans

        fs = getattr(obj, 'fontsize', None)
        if fs is not None:
            ans += item(f'font-size: {int(fs) / 10:f}pt;')
        fw = getattr(obj, 'fontweight', None)
        if fw is not None:
            ans += item('font-weight: {};'.format('bold' if int(fw) >= 700 else 'normal'))
        fn = getattr(obj, 'fontfacename', None)
        if fn is not None:
            fn = cls.FONT_MAP[fn]
            ans += item(f'font-family: {fn};')
        fg = getattr(obj, 'textcolor', None)
        if fg is not None:
            fg = fg.to_html()
            ans += item(f'color: {fg};')
        bg = getattr(obj, 'textbgcolor', None)
        if bg is not None:
            bg = bg.to_html()
            ans += item(f'background-color: {bg};')
        al = getattr(obj, 'align', None)
        if al is not None:
            al = dict(head='left', center='center', foot='right')
            ans += item(f'text-align: {al};')
        lh = getattr(obj, 'linespace', None)
        if lh is not None:
            ans += item(f'text-align: {int(lh) / 10:f}pt;')
        pi = getattr(obj, 'parindent', None)
        if pi is not None:
            ans += item(f'text-indent: {int(pi) / 10:f}pt;')

        return ans


class TextAttr(StyleObject, LRFObject, TextCSS):
    FONT_MAP = collections.defaultdict(lambda: 'serif')
    for key, value in PRS500_PROFILE.default_fonts.items():
        FONT_MAP[value] = key

    tag_map = {
        0xF511: ['fontsize', 'w'],
        0xF512: ['fontwidth', 'w'],
        0xF513: ['fontescapement', 'w'],
        0xF514: ['fontorientation', 'w'],
        0xF515: ['fontweight', 'W'],
        0xF516: ['fontfacename', 'P'],
        0xF517: ['textcolor', 'D', Color],
        0xF518: ['textbgcolor', 'D', Color],
        0xF519: ['wordspace', 'w'],
        0xF51A: ['letterspace', 'w'],
        0xF51B: ['baselineskip', 'w'],
        0xF51C: ['linespace', 'w'],
        0xF51D: ['parindent', 'w'],
        0xF51E: ['parskip', 'w'],
        0xF53C: ['align', 'W', {1: 'head', 4: 'center', 8: 'foot'}],
        0xF53D: ['column', 'W'],
        0xF53E: ['columnsep', 'W'],
        0xF5DD: ['charspace', 'w'],
        0xF5F1: ['textlinewidth', 'W'],
        0xF5F2: ['linecolor', 'D', Color],
    }
    tag_map.update(ruby_tags)
    tag_map.update(LRFObject.tag_map)


class Block(LRFStream, TextCSS):
    tag_map = {
        0xF503: ['style_id', 'D'],
    }
    tag_map.update(BlockAttr.tag_map)
    tag_map.update(TextAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    style_id: int  # set via tag_map[0xF503]
    bgcolor: Color  # set via tag_map[0xF534]
    framecolor: Color  # set via tag_map[0xF537]
    extra_attrs: ClassVar[list[str]] = [str(i[0]) for i in BlockAttr.tag_map.values()]
    extra_attrs = extra_attrs + [str(i[0]) for i in TextAttr.tag_map.values()]

    style = property(fget=lambda self: self._document.objects[self.style_id])
    textstyle = property(fget=lambda self: self._document.objects[self.textstyle_id])

    def initialize(self) -> None:
        self.attrs = {}
        raw = self.stream if isinstance(self.stream, bytes) else b''
        stream = io.BytesIO(raw)
        tag = Tag(stream)
        if tag.id != 0xF503:
            raise LRFParseError('Bad block content')
        obj = self._document.objects[tag.dword]
        if isinstance(obj, SimpleText):
            self.name = 'SimpleTextBlock'
            self.textstyle_id = obj.style_id
        elif isinstance(obj, Text):
            self.name = 'TextBlock'
            self.textstyle_id = obj.style_id
        elif isinstance(obj, Image):
            self.name = 'ImageBlock'
            for attr in ('x0', 'x1', 'y0', 'y1', 'xsize', 'ysize', 'refstream'):
                self.attrs[attr] = getattr(obj, attr)
            self.refstream = self._document.objects[self.attrs['refstream']]
        elif isinstance(obj, Button):
            self.name = 'ButtonBlock'
        else:
            raise LRFParseError('Unexpected block type: ' + obj.__class__.__name__)

        self.content = obj

        for attr in self.extra_attrs:
            if hasattr(self, attr):
                self.attrs[attr] = getattr(self, attr)

    def __str__(self) -> str:
        s = f"\n<{self.name} objid=\"{self.id}\" blockstyle=\"{getattr(self, 'style_id', '')}\" "
        if hasattr(self, 'textstyle_id'):
            s += f'textstyle="{self.textstyle_id}" '
        for attr in self.attrs:
            s += f'{attr}="{self.attrs[attr]}" '
        if self.name != 'ImageBlock':
            s = s.rstrip() + '>\n'
            s += str(self.content)
            s += f'</{self.name}>\n'
            return s
        return s.rstrip() + ' />\n'

    def to_html(self) -> str:
        if self.name == 'TextBlock':
            return f'<div class="block{self.style_id} text{self.textstyle_id}">{cast('Text', self.content).to_html()}</div>'
        return ''


class MiniPage(LRFStream):
    tag_map = {
        0xF541: ['minipagewidth', 'W'],
        0xF542: ['minipageheight', 'W'],
    }
    tag_map.update(LRFStream.tag_map)
    tag_map.update(BlockAttr.tag_map)


class Text(LRFStream):
    tag_map = {
        0xF503: ['style_id', 'D'],
    }
    tag_map.update(TextAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    style_id: int  # set via tag_map[0xF503]

    style = property(fget=lambda self: self._document.objects[self.style_id])

    text_map = {0x22: '"', 0x26: '&amp;', 0x27: "'", 0x3C: '&lt;', 0x3E: '&gt;'}
    entity_pattern = re.compile(r'&amp;(\S+?);')

    text_tags = {
        0xF581: ['simple_container', 'Italic'],
        0xF582: 'end_container',
        0xF5B1: ['simple_container', 'Yoko'],
        0xF5B2: 'end_container',
        0xF5B3: ['simple_container', 'Tate'],
        0xF5B4: 'end_container',
        0xF5B5: ['simple_container', 'Nekase'],
        0xF5B6: 'end_container',
        0xF5A1: 'start_para',
        0xF5A2: 'end_para',
        0xF5A7: 'char_button',
        0xF5A8: 'end_container',
        0xF5A9: ['simple_container', 'Rubi'],
        0xF5AA: 'end_container',
        0xF5AB: ['simple_container', 'Oyamoji'],
        0xF5AC: 'end_container',
        0xF5AD: ['simple_container', 'Rubimoji'],
        0xF5AE: 'end_container',
        0xF5B7: ['simple_container', 'Sup'],
        0xF5B8: 'end_container',
        0xF5B9: ['simple_container', 'Sub'],
        0xF5BA: 'end_container',
        0xF5BB: ['simple_container', 'NoBR'],
        0xF5BC: 'end_container',
        0xF5BD: ['simple_container', 'EmpDots'],
        0xF5BE: 'end_container',
        0xF5C1: 'empline',
        0xF5C2: 'end_container',
        0xF5C3: 'draw_char',
        0xF5C4: 'end_container',
        0xF5C6: 'box',
        0xF5C7: 'end_container',
        0xF5CA: 'space',
        0xF5D1: 'plot',
        0xF5D2: 'cr',
    }

    class TextTag:
        refobj: object  # set for Plot tags only

        def __init__(self, name: str, attrs: dict[str, object] | None = None, self_closing: bool = False) -> None:
            if attrs is None:
                attrs = {}
            self.name = name
            self.attrs = attrs
            self.self_closing = self_closing

        def __str__(self) -> str:
            s = f'<{self.name} '
            for name, val in self.attrs.items():
                s += f'{name}="{val}" '
            return s.rstrip() + (' />' if self.self_closing else '>')

        def to_html(self) -> str:
            s = ''
            return s

        def close_html(self) -> str:
            return ''

    class Span(TextTag):
        pass

    linetype_map = {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}
    adjustment_map = {1: 'top', 2: 'center', 3: 'baseline', 4: 'bottom'}
    lineposition_map = {1: 'before', 2: 'after'}

    def add_text(self, text: bytes) -> None:
        s = str(text, 'utf-16-le')
        if s:
            s = s.translate(self.text_map)
            self.content.append(self.entity_pattern.sub(entity_to_unicode_in_python, s))

    def end_container(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(None)

    def start_para(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('P'))

    def close_containers(self, start: int = 0) -> None:
        if len(self.content) == 0:
            return
        open_containers = 0
        if len(self.content) > 0 and isinstance(self.content[-1], self.__class__.Span):
            self.content.pop()
        while start < len(self.content):
            c = self.content[start]
            if c is None:
                open_containers -= 1
            elif isinstance(c, self.__class__.TextTag) and not c.self_closing:
                open_containers += 1
            start += 1
        self.content.extend(None for i in range(open_containers))

    def end_para(self, tag: Tag, stream: IO[bytes]) -> None:
        i = len(self.content) - 1
        while i > -1:
            if isinstance(self.content[i], Text.TextTag) and self.content[i].name == 'P':
                break
            i -= 1
        self.close_containers(start=i)

    def cr(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('CR', self_closing=True))

    def char_button(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('CharButton', attrs={'refobj': tag.dword}))

    def simple_container(self, tag: Tag, name: str) -> None:
        self.content.append(self.__class__.TextTag(name))

    def empline(self, tag: Tag, stream: IO[bytes]) -> None:
        def invalid(op: int) -> None:
            stream.seek(op)
            # self.simple_container(None, 'EmpLine')

        oldpos = stream.tell()
        try:
            t = Tag(stream)
            if t.id not in (0xF579, 0xF57A):
                raise LRFParseError
        except LRFParseError:
            invalid(oldpos)
            return
        h = TextAttr.tag_map[t.id]
        attrs: dict[str, object] = {}
        attrs[h[0]] = TextAttr.tag_to_val(h, None, t, None)
        oldpos = stream.tell()
        try:
            t = Tag(stream)
            if t.id not in (0xF579, 0xF57A):
                raise LRFParseError
            h = TextAttr.tag_map[t.id]
            attrs[h[0]] = TextAttr.tag_to_val(h, None, t, None)
        except LRFParseError:
            stream.seek(oldpos)

        if attrs:
            self.content.append(self.__class__.TextTag('EmpLine', attrs=attrs))

    def space(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('Space', attrs={'xsize': tag.sword}, self_closing=True))

    def plot(self, tag: Tag, stream: IO[bytes]) -> None:
        xsize, ysize, refobj, adjustment = struct.unpack('<HHII', tag.contents)
        plot = self.__class__.TextTag(
            'Plot',
            {'xsize': xsize, 'ysize': ysize, 'refobj': refobj, 'adjustment': self.adjustment_map[adjustment]},
            self_closing=True,
        )
        plot.refobj = self._document.objects[refobj]
        self.content.append(plot)

    def draw_char(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('DrawChar', {'line': tag.word}))

    def box(self, tag: Tag, stream: IO[bytes]) -> None:
        self.content.append(self.__class__.TextTag('Box', {'linetype': self.linetype_map[tag.word]}))

    def initialize(self) -> None:
        self.content = collections.deque()
        s: bytes = self.stream if isinstance(self.stream, bytes) else b''
        stream = io.BytesIO(s)
        length = len(s)
        style = self.style.as_dict()
        current_style = style.copy()
        text_tags = set(list(TextAttr.tag_map.keys()) + list(Text.text_tags.keys()) + list(ruby_tags.keys()))
        text_tags -= {0xF500 + i for i in range(10)}
        text_tags.add(0xF5CC)

        while stream.tell() < length:
            # Is there some text before a tag?
            def find_first_tag(start: int) -> int:
                pos = s.find(b'\xf5', start)
                if pos == -1:
                    return -1
                try:
                    stream.seek(pos - 1)
                    _t = Tag(stream)
                    if _t.id in text_tags:
                        return pos - 1
                    return find_first_tag(pos + 1)

                except Exception:
                    return find_first_tag(pos + 1)

            start_pos = stream.tell()
            tag_pos = find_first_tag(start_pos)
            if tag_pos >= start_pos:
                if tag_pos > start_pos:
                    self.add_text(s[start_pos:tag_pos])
                stream.seek(tag_pos)
            else:  # No tags in this stream
                self.add_text(s)
                stream.seek(0, 2)
                break

            tag = Tag(stream)

            if tag.id == 0xF5CC:
                self.add_text(stream.read(tag.word))
            elif tag.id in self.__class__.text_tags:  # A Text tag
                action = self.__class__.text_tags[tag.id]
                if isinstance(action, str):
                    getattr(self, action)(tag, stream)
                else:
                    getattr(self, action[0])(tag, action[1])
            elif tag.id in TextAttr.tag_map:  # A Span attribute
                action = TextAttr.tag_map[tag.id]
                if len(self.content) == 0:
                    current_style = style.copy()
                name, val = action[0], LRFObject.tag_to_val(action, self, tag, None)
                if name and (name not in current_style or current_style[name] != val):
                    # No existing Span
                    if len(self.content) > 0 and isinstance(self.content[-1], self.__class__.Span):
                        self.content[-1].attrs[name] = val
                    else:
                        self.content.append(self.__class__.Span('Span', {name: val}))
                    current_style[name] = val
        if len(self.content) > 0:
            self.close_containers()
        self.stream = None

    def __str__(self) -> str:
        s = ''
        open_containers = collections.deque()
        for c in self.content:
            if isinstance(c, str):
                s += prepare_string_for_xml(c).replace('\0', '')
            elif c is None:
                if open_containers:
                    p = open_containers.pop()
                    s += f'</{p.name}>'
            else:
                s += str(c)
                if not c.self_closing:
                    open_containers.append(c)

        if len(open_containers) > 0:
            if len(open_containers) == 1:
                s += f'</{open_containers[0].name}>'
            else:
                raise LRFParseError(f'Malformed text stream {[i.name for i in open_containers if isinstance(i, Text.TextTag)]}')
        return s

    def to_html(self) -> str:
        s = ''
        open_containers = collections.deque()
        in_p = False
        for c in self.content:
            if isinstance(c, str):
                s += c
            elif c is None:
                p = open_containers.pop()
                s += p.close_html()
            elif c.name == 'P':
                in_p = True
            elif c.name == 'CR':
                s += '<br />' if in_p else '<p>'
            else:
                s += c.to_html()
                if not c.self_closing:
                    open_containers.append(c)

        if len(open_containers) > 0:
            raise LRFParseError(f'Malformed text stream {[i.name for i in open_containers if isinstance(i, Text.TextTag)]}')
        return s


class Image(LRFObject):
    tag_map = {
        0xF54A: ['', 'parse_image_rect'],
        0xF54B: ['', 'parse_image_size'],
        0xF54C: ['refstream', 'D'],
        0xF555: ['comment', 'P'],
    }
    refstream: int  # set via tag_map[0xF54C]

    def parse_image_rect(self, tag: Tag, f: IO[bytes]) -> None:
        self.x0, self.y0, self.x1, self.y1 = struct.unpack('<HHHH', tag.contents)

    def parse_image_size(self, tag: Tag, f: IO[bytes]) -> None:
        self.xsize, self.ysize = struct.unpack('<HH', tag.contents)

    encoding = property(fget=lambda self: self._document.objects[self.refstream].encoding)
    data = property(fget=lambda self: self._document.objects[self.refstream].stream)

    def __str__(self) -> str:
        return (
            f'<Image objid="{self.id}" x0="{self.x0}" y0="{self.y0}" x1="{self.x1}" y1="{self.y1}"'
            f' xsize="{self.xsize}" ysize="{self.ysize}" refstream="{self.refstream}" />\n'
        )


class PutObj(EmptyPageElement):
    def __init__(self, objects: dict[int, LRFObject], x1: int, y1: int, refobj: int) -> None:
        self.x1, self.y1, self.refobj = x1, y1, refobj
        self.object = objects[refobj]

    def __str__(self) -> str:
        return f'<PutObj x1="{self.x1}" y1="{self.y1}" refobj="{self.refobj}" />'


class Canvas(LRFStream):
    tag_map = {
        0xF551: ['canvaswidth', 'W'],
        0xF552: ['canvasheight', 'W'],
        0xF5DA: ['', 'parse_waits'],
        0xF533: ['blockrule', 'W', {0x44: 'block-fixed', 0x22: 'block-adjustable'}],
        0xF534: ['bgcolor', 'D', Color],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W'],
        0xF537: ['framecolor', 'D', Color],
        0xF52E: ['framemode', 'W', {0: 'none', 2: 'curve', 1: 'square'}],
    }
    tag_map.update(LRFStream.tag_map)
    extra_attrs = ['canvaswidth', 'canvasheight', 'blockrule', 'layout', 'framewidth', 'framecolor', 'framemode']

    def parse_waits(self, tag: Tag, f: IO[bytes]) -> None:
        val = tag.word
        self.setwaitprop = val & 0xF
        self.setwaitsync = val & 0xF0

    def initialize(self) -> None:
        self.attrs = {}
        for attr in self.extra_attrs:
            if hasattr(self, attr):
                self.attrs[attr] = getattr(self, attr)
        self._contents = []
        s: bytes = self.stream if isinstance(self.stream, bytes) else b''
        stream = io.BytesIO(s)
        while stream.tell() < len(s):
            tag = Tag(stream)
            try:
                self._contents.append(PutObj(self._document.objects, *struct.unpack('<HHI', tag.contents)))
            except struct.error:
                print('Canvas object has errors, skipping.')

    def __str__(self) -> str:
        s = f'\n<{self.__class__.__name__} objid="{self.id}" '
        for attr in self.attrs:
            s += f'{attr}="{self.attrs[attr]}" '
        s = s.rstrip() + '>\n'
        for po in self:
            s += str(po) + '\n'
        s += f'</{self.__class__.__name__}>\n'
        return s

    def __iter__(self) -> Iterator[PutObj]:
        yield from self._contents


class Header(Canvas):
    pass


class Footer(Canvas):
    pass


class ESound(LRFObject):
    pass


class ImageStream(LRFStream):
    tag_map = {
        0xF555: ['comment', 'P'],
    }
    imgext = {0x11: 'jpeg', 0x12: 'png', 0x13: 'bmp', 0x14: 'gif'}

    tag_map.update(LRFStream.tag_map)

    encoding = property(fget=lambda self: self.imgext[self.stream_flags & 0xFF].upper())

    def end_stream(self, tag: Tag | None, stream: IO[bytes] | None) -> None:
        LRFStream.end_stream(self, tag, stream)
        self.file = str(self.id) + '.' + self.encoding.lower()
        if self._document is not None:
            self._document.image_map[self.id] = self

    def __str__(self) -> str:
        return f'<ImageStream objid="{self.id}" encoding="{self.encoding}" file="{self.file}" />\n'


class Import(LRFStream):
    pass


class Button(LRFObject):
    tag_map = {
        0xF503: ['', 'do_ref_image'],
        0xF561: ['button_flags', 'W'],  # <Button/>
        0xF562: ['', 'do_base_button'],  # <BaseButton>
        0xF563: ['', ''],  # </BaseButton>
        0xF564: ['', 'do_focus_in_button'],  # <FocusinButton>
        0xF565: ['', ''],  # </FocusinButton>
        0xF566: ['', 'do_push_button'],  # <PushButton>
        0xF567: ['', ''],  # </PushButton>
        0xF568: ['', 'do_up_button'],  # <UpButton>
        0xF569: ['', ''],  # </UpButton>
        0xF56A: ['', 'do_start_actions'],  # start actions
        0xF56B: ['', ''],  # end actions
        0xF56C: ['', 'parse_jump_to'],  # JumpTo
        0xF56D: ['', 'parse_send_message'],  # <SendMessage
        0xF56E: ['', 'parse_close_window'],  # <CloseWindow/>
        0xF5D6: ['', 'parse_sound_stop'],  # <SoundStop/>
        0xF5F9: ['', 'parse_run'],  # Run
    }
    tag_map.update(LRFObject.tag_map)
    button_flags: int  # set via tag_map[0xF561]

    def __init__(self, document: LRFDocument | None, stream: IO[bytes], id: int, scramble_key: int, boundary: int) -> None:
        self.xml = ''
        self.refimage = {}
        self.actions = {}
        self.to_dump = True
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)

    def do_ref_image(self, tag: Tag, f: IO[bytes]) -> None:
        self.refimage[self.button_type] = tag.dword

    def do_base_button(self, tag: Tag, f: IO[bytes]) -> None:
        self.button_type = 0
        self.actions[self.button_type] = []

    def do_focus_in_button(self, tag: Tag, f: IO[bytes]) -> None:
        self.button_type = 1

    def do_push_button(self, tag: Tag, f: IO[bytes]) -> None:
        self.button_type = 2

    def do_up_button(self, tag: Tag, f: IO[bytes]) -> None:
        self.button_type = 3

    def do_start_actions(self, tag: Tag, f: IO[bytes]) -> None:
        self.actions[self.button_type] = []

    def parse_jump_to(self, tag: Tag, f: IO[bytes]) -> None:
        self.actions[self.button_type].append((1, struct.unpack('<II', tag.contents)))

    def parse_send_message(self, tag: Tag, f: IO[bytes]) -> None:
        params = (tag.word, Tag.string_parser(f), Tag.string_parser(f))
        self.actions[self.button_type].append((2, params))

    def parse_close_window(self, tag: Tag, f: IO[bytes]) -> None:
        self.actions[self.button_type].append((3,))

    def parse_sound_stop(self, tag: Tag, f: IO[bytes]) -> None:
        self.actions[self.button_type].append((4,))

    def parse_run(self, tag: Tag, f: IO[bytes]) -> None:
        self.actions[self.button_type].append((5, struct.unpack('<HI', tag.contents)))

    def jump_action(self, button_type: int) -> tuple[int, int] | tuple[None, None]:
        for i in self.actions[button_type]:
            if i[0] == 1:
                return i[1:][0]
        return None, None

    def __str__(self) -> str:
        s = f'<Button objid="{self.id}">\n'
        if self.button_flags & 0x10 != 0:
            s += '<PushButton '
            if 2 in self.refimage:
                s += f'refimage="{self.refimage[2]}" '
            s = s.rstrip() + '>\n'
            s += '<JumpTo refpage="{}" refobj="{}" />\n'.format(*self.jump_action(2))
            s += '</PushButton>\n'
        else:
            raise LRFParseError('Unsupported button type')
        s += '</Button>\n'
        return s

    refpage = property(fget=lambda self: self.jump_action(2)[0])
    refobj = property(fget=lambda self: self.jump_action(2)[1])


class Window(LRFObject):
    pass


class PopUpWin(LRFObject):
    pass


class Sound(LRFObject):
    pass


class SoundStream(LRFObject):
    pass


class Font(LRFStream):
    tag_map = {
        0xF559: ['fontfilename', 'P'],
        0xF55D: ['fontfacename', 'P'],
    }
    tag_map.update(LRFStream.tag_map)
    fontfilename: str  # set via tag_map[0xF559]
    fontfacename: str  # set via tag_map[0xF55D]
    data = property(fget=lambda self: self.stream)

    def end_stream(self, tag: Tag | None, stream: IO[bytes] | None) -> None:
        LRFStream.end_stream(self, tag, stream)
        self._document.font_map[self.fontfacename] = self
        self.file = self.fontfacename + '.ttf'

    def __unicode__(self) -> str:
        s = f'<RegistFont objid="{self.id}" fontfilename="{self.fontfilename}" fontname="{self.fontfacename}" encoding="TTF" file="{self.file}" />\n'
        return s


class ObjectInfo(LRFStream):
    pass


class BookAttr(StyleObject, LRFObject):
    tag_map = {
        0xF57B: ['page_tree_id', 'D'],
        0xF5D8: ['', 'add_font'],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
    }
    tag_map.update(ruby_tags)
    tag_map.update(LRFObject.tag_map)
    binding_map = {1: 'Lr', 16: 'Rl'}

    def __init__(self, document: LRFDocument | None, stream: IO[bytes], id: int, scramble_key: int, boundary: int) -> None:
        self.font_link_list: list[int] = []
        LRFObject.__init__(self, document, stream, id, scramble_key, boundary)

    def add_font(self, tag: Tag, f: IO[bytes]) -> None:
        self.font_link_list.append(tag.dword)

    def __str__(self) -> str:
        s = f'<BookStyle objid="{self.id}" stylelabel="{self.id}">\n'
        s += f'<SetDefault {self._tags_to_xml()} />\n'
        doc = self._document
        s += f'<BookSetting bindingdirection="{self.binding_map[doc.binding]}" dpi="{doc.dpi}" screenwidth="{doc.width}"'
        s += f' screenheight="{doc.height}" colordepth="{doc.color_depth}" />\n'
        for font in self._document.font_map.values():
            s += str(font)
        s += '</BookStyle>\n'
        return s


class SimpleText(Text):
    pass


class TocLabel:
    def __init__(self, refpage: int, refobject: int, label: str) -> None:
        self.refpage, self.refobject, self.label = refpage, refobject, label

    def __str__(self) -> str:
        return f'<TocLabel refpage="{self.refpage}" refobj="{self.refobject}">{self.label}</TocLabel>\n'


class TOCObject(LRFStream):
    def initialize(self) -> None:
        stream = io.BytesIO(self.stream if isinstance(self.stream, bytes) else b'')
        c = struct.unpack('<H', stream.read(2))[0]
        stream.seek(4 * (c + 1))
        self._contents = []
        while c > 0:
            refpage = struct.unpack('<I', stream.read(4))[0]
            refobj = struct.unpack('<I', stream.read(4))[0]
            cnt = struct.unpack('<H', stream.read(2))[0]
            raw = stream.read(cnt)
            label = raw.decode('utf_16_le')
            self._contents.append(TocLabel(refpage, refobj, label))
            c -= 1

    def __iter__(self) -> Iterator[TocLabel]:
        yield from self._contents

    def __str__(self) -> str:
        s = '<TOC>\n'
        for i in self:
            s += str(i)
        return s + '</TOC>\n'


object_map = [
    None,  # 00
    PageTree,  # 01
    Page,  # 02
    Header,  # 03
    Footer,  # 04
    PageAttr,  # 05
    Block,  # 06
    BlockAttr,  # 07
    MiniPage,  # 08
    None,  # 09
    Text,  # 0A
    TextAttr,  # 0B
    Image,  # 0C
    Canvas,  # 0D
    ESound,  # 0E
    None,  # 0F
    None,  # 10
    ImageStream,  # 11
    Import,  # 12
    Button,  # 13
    Window,  # 14
    PopUpWin,  # 15
    Sound,  # 16
    SoundStream,  # 17
    None,  # 18
    Font,  # 19
    ObjectInfo,  # 1A
    None,  # 1B
    BookAttr,  # 1C
    SimpleText,  # 1D
    TOCObject,  # 1E
]


def get_object(document: LRFDocument | None, stream: IO[bytes], id: int, offset: int, size: int, scramble_key: int) -> LRFObject:
    stream.seek(offset)
    start_tag = Tag(stream)
    if start_tag.id != 0xF500:
        raise LRFParseError('Bad object start')
    obj_id, obj_type = struct.unpack('<IH', start_tag.contents)
    if obj_type < len(object_map):
        obj_cls = object_map[obj_type]
        if obj_cls is not None:
            return obj_cls(document, stream, obj_id, scramble_key, offset + size - cast('int', Tag.tags[0][0]))  # ObjectStart has a fixed size

    raise LRFParseError(f'Unknown object type: {obj_type:02X}!')
