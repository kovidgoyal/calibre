'''
Basic support for writing LIT files.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from struct import pack
from itertools import count, chain
from operator import attrgetter
import io
import time
import os
import re
import copy
import uuid
import functools
import numbers
from lxml import etree
from calibre.ebooks.lit.reader import DirectoryEntry
import calibre.ebooks.lit.maps as maps
from calibre.ebooks.oeb.base import OEB_DOCS, XHTML_MIME, OEB_STYLES, \
    CSS_MIME, OPF_MIME, XML_NS, XML
from calibre.ebooks.oeb.base import prefixname, \
    urlnormalize
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.lit.lzx import Compressor
import calibre
from calibre_extensions import msdes
import calibre.ebooks.lit.mssha1 as mssha1
from polyglot.builtins import codepoint_to_chr, string_or_bytes, native_string_type
from polyglot.urllib import urldefrag, unquote

__all__ = ['LitWriter']

LIT_IMAGES = {'image/png', 'image/jpeg', 'image/gif'}
LIT_MIMES = OEB_DOCS | OEB_STYLES | LIT_IMAGES

MS_COVER_TYPE = 'other.ms-coverimage-standard'
ALL_MS_COVER_TYPES = [
    (MS_COVER_TYPE, 'Standard cover image'),
    ('other.ms-thumbimage-standard', 'Standard thumbnail image'),
    ('other.ms-coverimage', 'PocketPC cover image'),
    ('other.ms-thumbimage', 'PocketPC thumbnail image'),
    ]


def invert_tag_map(tag_map):
    tags, dattrs, tattrs = tag_map
    tags = {tags[i]: i for i in range(len(tags))}
    dattrs = {v: k for k, v in dattrs.items()}
    tattrs = [{v: k for k, v in (map or {}).items()} for map in tattrs]
    for map in tattrs:
        if map:
            map.update(dattrs)
    tattrs[0] = dattrs
    return tags, tattrs


OPF_MAP = invert_tag_map(maps.OPF_MAP)
HTML_MAP = invert_tag_map(maps.HTML_MAP)

LIT_MAGIC = b'ITOLITLS'

LITFILE_GUID = "{0A9007C1-4076-11D3-8789-0000F8105754}"
PIECE3_GUID = "{0A9007C3-4076-11D3-8789-0000F8105754}"
PIECE4_GUID = "{0A9007C4-4076-11D3-8789-0000F8105754}"
DESENCRYPT_GUID = "{67F6E4A2-60BF-11D3-8540-00C04F58C3CF}"
LZXCOMPRESS_GUID = "{0A9007C6-4076-11D3-8789-0000F8105754}"


def packguid(guid):
    values = guid[1:9], guid[10:14], guid[15:19], \
        guid[20:22], guid[22:24], guid[25:27], guid[27:29], \
        guid[29:31], guid[31:33], guid[33:35], guid[35:37]
    values = [int(value, 16) for value in values]
    return pack("<LHHBBBBBBBB", *values)


FLAG_OPENING = (1 << 0)
FLAG_CLOSING = (1 << 1)
FLAG_BLOCK = (1 << 2)
FLAG_HEAD = (1 << 3)
FLAG_ATOM = (1 << 4)
FLAG_CUSTOM  = (1 << 15)
ATTR_NUMBER  = 0xffff

PIECE_SIZE = 16
PRIMARY_SIZE = 40
SECONDARY_SIZE = 232
DCHUNK_SIZE = 0x2000
CCHUNK_SIZE = 0x0200
ULL_NEG1 = 0xffffffffffffffff
ROOT_OFFSET = 1284508585713721976
ROOT_SIZE = 4165955342166943123

BLOCK_CAOL = \
    b"\x43\x41\x4f\x4c\x02\x00\x00\x00" \
    b"\x50\x00\x00\x00\x37\x13\x03\x00" \
    b"\x00\x00\x00\x00\x00\x20\x00\x00" \
    b"\x00\x02\x00\x00\x00\x00\x10\x00" \
    b"\x00\x00\x02\x00\x00\x00\x00\x00" \
    b"\x00\x00\x00\x00\x00\x00\x00\x00"
BLOCK_ITSF = \
    b"\x49\x54\x53\x46\x04\x00\x00\x00" \
    b"\x20\x00\x00\x00\x01\x00\x00\x00"

MSDES_CONTROL = \
    b"\x03\x00\x00\x00\x29\x17\x00\x00" \
    b"\x01\x00\x00\x00\xa5\xa5\x00\x00"
LZXC_CONTROL = \
    b"\x07\x00\x00\x00\x4c\x5a\x58\x43" \
    b"\x03\x00\x00\x00\x04\x00\x00\x00" \
    b"\x04\x00\x00\x00\x02\x00\x00\x00" \
    b"\x00\x00\x00\x00\x00\x00\x00\x00"

COLLAPSE = re.compile(r'[ \t\r\n\v]+')

PAGE_BREAKS = {'always', 'left', 'right'}


def decint(value):
    ans = bytearray()
    while True:
        b = value & 0x7f
        value >>= 7
        if len(ans):
            b |= 0x80
        ans.append(b)
        if value == 0:
            break
    return bytes(bytearray(reversed(ans)))


randbytes = os.urandom


def warn(x):
    print(x)


class ReBinary:
    NSRMAP = {'': None, XML_NS: 'xml'}

    def __init__(self, root, item, oeb, opts, map=HTML_MAP):
        self.item = item
        self.logger = oeb.logger
        self.manifest = oeb.manifest
        self.tags, self.tattrs = map
        self.buf = io.BytesIO()
        self.anchors = []
        self.page_breaks = []
        self.is_html  = is_html = map is HTML_MAP
        self.stylizer = Stylizer(root, item.href, oeb, opts) if is_html else None
        self.tree_to_binary(root)
        self.content = self.buf.getvalue()
        self.ahc = self.build_ahc() if is_html else None
        self.aht = self.build_aht() if is_html else None

    def write(self, *values):
        for value in values:
            if isinstance(value, numbers.Integral):
                try:
                    value = codepoint_to_chr(value)
                except OverflowError:
                    self.logger.warn('Unicode overflow for integer:', value)
                    value = '?'
            self.buf.write(value.encode('utf-8'))

    def is_block(self, style):
        return style['display'] not in ('inline', 'inline-block')

    def tree_to_binary(self, elem, nsrmap=NSRMAP, parents=[],
                       inhead=False, preserve=False):
        if not isinstance(elem.tag, string_or_bytes):
            # Don't emit any comments or raw entities
            return
        nsrmap = copy.copy(nsrmap)
        attrib = dict(elem.attrib)
        style = self.stylizer.style(elem) if self.stylizer else None
        for key, value in elem.nsmap.items():
            if value not in nsrmap or nsrmap[value] != key:
                xmlns = ('xmlns:' + key) if key else 'xmlns'
                attrib[xmlns] = value
            nsrmap[value] = key
        tag = prefixname(elem.tag, nsrmap)
        tag_offset = self.buf.tell()
        if tag == 'head':
            inhead = True
        flags = FLAG_OPENING
        if not elem.text and len(elem) == 0:
            flags |= FLAG_CLOSING
        if inhead:
            flags |= FLAG_HEAD
        if style and self.is_block(style):
            flags |= FLAG_BLOCK
        self.write(0, flags)
        tattrs = self.tattrs[0]
        if tag in self.tags:
            index = self.tags[tag]
            self.write(index)
            if self.tattrs[index]:
                tattrs = self.tattrs[index]
        else:
            self.write(FLAG_CUSTOM, len(tag)+1, tag)
        last_break = self.page_breaks[-1][0] if self.page_breaks else None
        if style and last_break != tag_offset \
           and style['page-break-before'] in PAGE_BREAKS:
            self.page_breaks.append((tag_offset, list(parents)))
        for attr, value in attrib.items():
            attr = prefixname(attr, nsrmap)
            if attr in ('href', 'src'):
                value = urlnormalize(value)
                path, frag = urldefrag(value)
                if self.item:
                    path = self.item.abshref(path)
                prefix = codepoint_to_chr(3)
                if path in self.manifest.hrefs:
                    prefix = codepoint_to_chr(2)
                    value = self.manifest.hrefs[path].id
                    if frag:
                        value = '#'.join((value, frag))
                value = prefix + value
            elif attr in ('id', 'name'):
                self.anchors.append((value, tag_offset))
            elif attr.startswith('ms--'):
                attr = '%' + attr[4:]
            elif tag == 'link' and attr == 'type' and value in OEB_STYLES:
                value = CSS_MIME
            if attr in tattrs:
                self.write(tattrs[attr])
            else:
                self.write(FLAG_CUSTOM, len(attr)+1, attr)
            try:
                self.write(ATTR_NUMBER, int(value)+1)
            except ValueError:
                self.write(len(value)+1, value)
        self.write(0)
        old_preserve = preserve
        if style:
            preserve = (style['white-space'] in ('pre', 'pre-wrap'))
        xml_space = elem.get(XML('space'))
        if xml_space == 'preserve':
            preserve = True
        elif xml_space == 'normal':
            preserve = False
        if elem.text:
            if preserve:
                self.write(elem.text)
            elif len(elem) == 0 or not elem.text.isspace():
                self.write(COLLAPSE.sub(' ', elem.text))
            # else: de nada
        parents.append(tag_offset)
        child = cstyle = nstyle = None
        for next in chain(elem, [None]):
            if self.stylizer:
                nstyle = None if next is None else self.stylizer.style(next)
            if child is not None:
                if not preserve \
                   and (inhead or not nstyle or self.is_block(cstyle) or self.is_block(nstyle)) \
                   and child.tail and child.tail.isspace():
                    child.tail = None
                self.tree_to_binary(child, nsrmap, parents, inhead, preserve)
            child, cstyle = next, nstyle
        parents.pop()
        preserve = old_preserve
        if not flags & FLAG_CLOSING:
            self.write(0, (flags & ~FLAG_OPENING) | FLAG_CLOSING, 0)
        if elem.tail and tag != 'html':
            tail = elem.tail
            if not preserve:
                tail = COLLAPSE.sub(' ', tail)
            self.write(tail)
        if style and style['page-break-after'] not in ('avoid', 'auto'):
            self.page_breaks.append((self.buf.tell(), list(parents)))

    def build_ahc(self):
        if len(self.anchors) > 6:
            self.logger.warn("More than six anchors in file %r. "
                "Some links may not work properly." % self.item.href)
        data = io.BytesIO()
        data.write(codepoint_to_chr(len(self.anchors)).encode('utf-8'))
        for anchor, offset in self.anchors:
            data.write(codepoint_to_chr(len(anchor)).encode('utf-8'))
            if isinstance(anchor, str):
                anchor = anchor.encode('utf-8')
            data.write(anchor)
            data.write(pack('<I', offset))
        return data.getvalue()

    def build_aht(self):
        return pack('<I', 0)


def preserve(function):
    def wrapper(self, *args, **kwargs):
        opos = self._stream.tell()
        try:
            return function(self, *args, **kwargs)
        finally:
            self._stream.seek(opos)
    functools.update_wrapper(wrapper, function)
    return wrapper


class LitWriter:

    def __init__(self, opts):
        self.opts = opts

    def _litize_oeb(self):
        oeb = self._oeb
        oeb.metadata.add('calibre-version', calibre.__version__)
        cover = None
        if oeb.metadata.cover:
            id = str(oeb.metadata.cover[0])
            cover = oeb.manifest.ids[id]
            for type, title in ALL_MS_COVER_TYPES:
                if type not in oeb.guide:
                    oeb.guide.add(type, title, cover.href)
        else:
            self._logger.warn('No suitable cover image found.')

    def __call__(self, oeb, path):
        if hasattr(path, 'write'):
            return self._dump_stream(oeb, path)
        with open(path, 'w+b') as stream:
            return self._dump_stream(oeb, stream)

    def _dump_stream(self, oeb, stream):
        self._oeb = oeb
        self._logger = oeb.logger
        self._stream = stream
        self._sections = [io.BytesIO() for i in range(4)]
        self._directory = []
        self._meta = None
        self._litize_oeb()
        self._write_content()

    def _write(self, *data):
        for datum in data:
            self._stream.write(datum)

    @preserve
    def _writeat(self, pos, *data):
        self._stream.seek(pos)
        self._write(*data)

    def _tell(self):
        return self._stream.tell()

    def _write_content(self):
        # Build content sections
        self._build_sections()

        # Build directory chunks
        dcounts, dchunks, ichunk = self._build_dchunks()

        # Write headers
        self._write(LIT_MAGIC)
        self._write(pack('<IIII',
            1, PRIMARY_SIZE, 5, SECONDARY_SIZE))
        self._write(packguid(LITFILE_GUID))
        offset = self._tell()
        pieces = list(range(offset, offset + (PIECE_SIZE * 5), PIECE_SIZE))
        self._write((5 * PIECE_SIZE) * b'\0')
        aoli1 = len(dchunks) if ichunk else ULL_NEG1
        last = len(dchunks) - 1
        ddepth = 2 if ichunk else 1
        self._write(pack('<IIQQQQIIIIQIIQQQQIIIIQIIIIQ',
            2, 0x98, aoli1, 0, last, 0, DCHUNK_SIZE, 2, 0, ddepth, 0,
            len(self._directory), 0, ULL_NEG1, 0, 0, 0, CCHUNK_SIZE, 2,
            0, 1, 0, len(dcounts), 0, 0x100000, 0x20000, 0))
        self._write(BLOCK_CAOL)
        self._write(BLOCK_ITSF)
        conoff_offset = self._tell()
        timestamp = int(time.time())
        self._write(pack('<QII', 0, timestamp, 0x409))

        # Piece #0
        piece0_offset = self._tell()
        self._write(pack('<II', 0x1fe, 0))
        filesz_offset = self._tell()
        self._write(pack('<QQ', 0, 0))
        self._writeat(pieces[0], pack('<QQ',
            piece0_offset, self._tell() - piece0_offset))

        # Piece #1: Directory chunks
        piece1_offset = self._tell()
        number = len(dchunks) + ((ichunk and 1) or 0)
        self._write(b'IFCM', pack('<IIIQQ',
            1, DCHUNK_SIZE, 0x100000, ULL_NEG1, number))
        for dchunk in dchunks:
            self._write(dchunk)
        if ichunk:
            self._write(ichunk)
        self._writeat(pieces[1], pack('<QQ',
            piece1_offset, self._tell() - piece1_offset))

        # Piece #2: Count chunks
        piece2_offset = self._tell()
        self._write(b'IFCM', pack('<IIIQQ',
            1, CCHUNK_SIZE, 0x20000, ULL_NEG1, 1))
        cchunk = io.BytesIO()
        last = 0
        for i, dcount in zip(count(), dcounts):
            cchunk.write(decint(last))
            cchunk.write(decint(dcount))
            cchunk.write(decint(i))
            last = dcount
        cchunk = cchunk.getvalue()
        rem = CCHUNK_SIZE - (len(cchunk) + 50)
        self._write(b'AOLL', pack('<IQQQQQ',
            rem, 0, ULL_NEG1, ULL_NEG1, 0, 1))
        filler = b'\0' * rem
        self._write(cchunk, filler, pack('<H', len(dcounts)))
        self._writeat(pieces[2], pack('<QQ',
            piece2_offset, self._tell() - piece2_offset))

        # Piece #3: GUID3
        piece3_offset = self._tell()
        self._write(packguid(PIECE3_GUID))
        self._writeat(pieces[3], pack('<QQ',
            piece3_offset, self._tell() - piece3_offset))

        # Piece #4: GUID4
        piece4_offset = self._tell()
        self._write(packguid(PIECE4_GUID))
        self._writeat(pieces[4], pack('<QQ',
            piece4_offset, self._tell() - piece4_offset))

        # The actual section content
        content_offset = self._tell()
        self._writeat(conoff_offset, pack('<Q', content_offset))
        self._write(self._sections[0].getvalue())
        self._writeat(filesz_offset, pack('<Q', self._tell()))

    def _add_file(self, name, data, secnum=0):
        if len(data) > 0:
            section = self._sections[secnum]
            offset = section.tell()
            section.write(data)
        else:
            offset = 0
        self._directory.append(
            DirectoryEntry(name, secnum, offset, len(data)))

    def _add_folder(self, name, offset=0, size=0):
        if not name.endswith('/'):
            name += '/'
        self._directory.append(
            DirectoryEntry(name, 0, offset, size))

    def _djoin(self, *names):
        return '/'.join(names)

    def _build_sections(self):
        self._add_folder('/', ROOT_OFFSET, ROOT_SIZE)
        self._build_data()
        self._build_manifest()
        self._build_page_breaks()
        self._build_meta()
        self._build_drm_storage()
        self._build_version()
        self._build_namelist()
        self._build_storage()
        self._build_transforms()

    def _build_data(self):
        self._add_folder('/data')
        for item in self._oeb.manifest.values():
            if item.media_type not in LIT_MIMES:
                self._logger.warn("File %r of unknown media-type %r "
                    "excluded from output." % (item.href, item.media_type))
                continue
            name = '/data/' + item.id
            data = item.data
            secnum = 0
            if isinstance(data, etree._Element):
                self._add_folder(name)
                rebin = ReBinary(data, item, self._oeb, self.opts, map=HTML_MAP)
                self._add_file(name + '/ahc', rebin.ahc, 0)
                self._add_file(name + '/aht', rebin.aht, 0)
                item.page_breaks = rebin.page_breaks
                data = rebin.content
                name = name + '/content'
                secnum = 1
            elif isinstance(data, str):
                data = data.encode('utf-8')
            elif hasattr(data, 'cssText'):
                data = item.bytes_representation
            self._add_file(name, data, secnum)
            item.size = len(data)

    def _build_manifest(self):
        states = ['linear', 'nonlinear', 'css', 'images']
        manifest = {state: [] for state in states}
        for item in self._oeb.manifest.values():
            if item.spine_position is not None:
                key = 'linear' if item.linear else 'nonlinear'
                manifest[key].append(item)
            elif item.media_type in OEB_STYLES:
                manifest['css'].append(item)
            elif item.media_type in LIT_IMAGES:
                manifest['images'].append(item)
        data = io.BytesIO()
        data.write(pack('<Bc', 1, b'\\'))
        offset = 0
        for state in states:
            items = sorted(manifest[state], key=attrgetter('sort_key'))
            data.write(pack('<I', len(items)))
            for item in items:
                id, media_type = item.id, item.media_type
                if media_type in OEB_DOCS:
                    # Needs to have 'html' in media-type
                    media_type = XHTML_MIME
                elif media_type in OEB_STYLES:
                    media_type = CSS_MIME
                href = unquote(item.href)
                item.offset = offset \
                    if state in ('linear', 'nonlinear') else 0
                data.write(pack('<I', item.offset))
                entry = [codepoint_to_chr(len(id)), str(id),
                         codepoint_to_chr(len(href)), str(href),
                         codepoint_to_chr(len(media_type)), str(media_type)]
                for value in entry:
                    data.write(value.encode('utf-8'))
                data.write(b'\0')
                offset += item.size
        self._add_file('/manifest', data.getvalue())

    def _build_page_breaks(self):
        pb1 = io.BytesIO()
        pb2 = io.BytesIO()
        pb3 = io.BytesIO()
        pb3cur = 0
        bits = 0
        linear = []
        nonlinear = []
        for item in self._oeb.spine:
            dest = linear if item.linear else nonlinear
            dest.append(item)
        for item in chain(linear, nonlinear):
            page_breaks = copy.copy(item.page_breaks)
            if not item.linear:
                page_breaks.insert(0, (0, []))
            for pbreak, parents in page_breaks:
                pb3cur = (pb3cur << 2) | 1
                if len(parents) > 1:
                    pb3cur |= 0x2
                bits += 2
                if bits >= 8:
                    pb3.write(pack('<B', pb3cur))
                    pb3cur = 0
                    bits = 0
                pbreak += item.offset
                pb1.write(pack('<II', pbreak, pb2.tell()))
                pb2.write(pack('<I', len(parents)))
                for parent in parents:
                    pb2.write(pack('<I', parent))
        if bits != 0:
            pb3cur <<= (8 - bits)
            pb3.write(pack('<B', pb3cur))
        self._add_file('/pb1', pb1.getvalue(), 0)
        self._add_file('/pb2', pb2.getvalue(), 0)
        self._add_file('/pb3', pb3.getvalue(), 0)

    def _build_meta(self):
        _, meta = self._oeb.to_opf1()[OPF_MIME]
        meta.attrib['ms--minimum_level'] = '0'
        meta.attrib['ms--attr5'] = '1'
        meta.attrib['ms--guid'] = '{%s}' % native_string_type(uuid.uuid4()).upper()
        rebin = ReBinary(meta, None, self._oeb, self.opts, map=OPF_MAP)
        meta = rebin.content
        self._meta = meta
        self._add_file('/meta', meta)

    def _build_drm_storage(self):
        drmsource = 'Free as in freedom\0'.encode('utf-16-le')
        self._add_file('/DRMStorage/DRMSource', drmsource)
        tempkey = self._calculate_deskey([self._meta, drmsource])
        msdes.deskey(tempkey, msdes.EN0)
        self._add_file('/DRMStorage/DRMSealed', msdes.des(b"\0" * 16))
        self._bookkey = b'\0' * 8
        self._add_file('/DRMStorage/ValidationStream', b'MSReader', 3)

    def _build_version(self):
        self._add_file('/Version', pack('<HH', 8, 1))

    def _build_namelist(self):
        data = io.BytesIO()
        data.write(pack('<HH', 0x3c, len(self._sections)))
        names = ['Uncompressed', 'MSCompressed', 'EbEncryptDS',
                 'EbEncryptOnlyDS']
        for name in names:
            data.write(pack('<H', len(name)))
            data.write(name.encode('utf-16-le'))
            data.write(b'\0\0')
        self._add_file('::DataSpace/NameList', data.getvalue())

    def _build_storage(self):
        mapping = [(1, 'MSCompressed', (LZXCOMPRESS_GUID,)),
                   (2, 'EbEncryptDS', (LZXCOMPRESS_GUID, DESENCRYPT_GUID)),
                   (3, 'EbEncryptOnlyDS', (DESENCRYPT_GUID,)),]
        for secnum, name, transforms in mapping:
            root = '::DataSpace/Storage/' + name
            data = self._sections[secnum].getvalue()
            cdata, sdata, tdata, rdata = b'', b'', b'', b''
            for guid in transforms:
                tdata = packguid(guid) + tdata
                sdata = sdata + pack('<Q', len(data))
                if guid == DESENCRYPT_GUID:
                    cdata = MSDES_CONTROL + cdata
                    if not data:
                        continue
                    msdes.deskey(self._bookkey, msdes.EN0)
                    pad = 8 - (len(data) & 0x7)
                    if pad != 8:
                        data = data + (b'\0' * pad)
                    data = msdes.des(data)
                elif guid == LZXCOMPRESS_GUID:
                    cdata = LZXC_CONTROL + cdata
                    if not data:
                        continue
                    unlen = len(data)
                    lzx = Compressor(17)
                    data, rtable = lzx.compress(data, flush=True)
                    rdata = io.BytesIO()
                    rdata.write(pack('<IIIIQQQQ',
                        3, len(rtable), 8, 0x28, unlen, len(data), 0x8000, 0))
                    for uncomp, comp in rtable[:-1]:
                        rdata.write(pack('<Q', comp))
                    rdata = rdata.getvalue()
            self._add_file(root + '/Content', data)
            self._add_file(root + '/ControlData', cdata)
            self._add_file(root + '/SpanInfo', sdata)
            self._add_file(root + '/Transform/List', tdata)
            troot = root + '/Transform'
            for guid in transforms:
                dname = self._djoin(troot, guid, 'InstanceData')
                self._add_folder(dname)
                if guid == LZXCOMPRESS_GUID:
                    dname += '/ResetTable'
                    self._add_file(dname, rdata)

    def _build_transforms(self):
        for guid in (LZXCOMPRESS_GUID, DESENCRYPT_GUID):
            self._add_folder('::Transform/'+ guid)

    def _calculate_deskey(self, hashdata):
        prepad = 2
        hash = mssha1.new()
        for data in hashdata:
            if prepad > 0:
                data = (b"\000" * prepad) + data
                prepad = 0
            postpad = 64 - (len(data) % 64)
            if postpad < 64:
                data = data + (b"\000" * postpad)
            hash.update(data)
        digest = hash.digest()
        if not isinstance(digest, bytes):
            digest = digest.encode('ascii')
        digest = bytearray(digest)
        key = bytearray(8)
        for i, k in enumerate(digest):
            key[i % 8] ^= k
        return bytes(key)

    def _build_dchunks(self):
        ddata = []
        directory = list(self._directory)
        directory.sort(key=lambda x: x.name.lower())
        qrn = 1 + (1 << 2)
        dchunk = io.BytesIO()
        dcount = 0
        quickref = []
        name = directory[0].name
        for entry in directory:
            en = entry.name
            if not isinstance(en, bytes):
                en = en.encode('utf-8')
            nxt = b''.join([decint(len(en)), en,
                decint(entry.section), decint(entry.offset),
                decint(entry.size)])
            usedlen = dchunk.tell() + len(nxt) + (len(quickref) * 2) + 52
            if usedlen >= DCHUNK_SIZE:
                ddata.append((dchunk.getvalue(), quickref, dcount, name))
                dchunk = io.BytesIO()
                dcount = 0
                quickref = []
                name = en
            if (dcount % qrn) == 0:
                quickref.append(dchunk.tell())
            dchunk.write(nxt)
            dcount = dcount + 1
        ddata.append((dchunk.getvalue(), quickref, dcount, name))
        cidmax = len(ddata) - 1
        rdcount = 0
        dchunks = []
        dcounts = []
        ichunk = None
        if len(ddata) > 1:
            ichunk = io.BytesIO()
        for cid, (content, quickref, dcount, name) in zip(count(), ddata):
            dchunk = io.BytesIO()
            prev = cid - 1 if cid > 0 else ULL_NEG1
            next = cid + 1 if cid < cidmax else ULL_NEG1
            rem = DCHUNK_SIZE - (len(content) + 50)
            pad = rem - (len(quickref) * 2)
            dchunk.write(b'AOLL')
            dchunk.write(pack('<IQQQQQ', rem, cid, prev, next, rdcount, 1))
            dchunk.write(content)
            dchunk.write(b'\0' * pad)
            for ref in reversed(quickref):
                dchunk.write(pack('<H', ref))
            dchunk.write(pack('<H', dcount))
            rdcount = rdcount + dcount
            dchunks.append(dchunk.getvalue())
            dcounts.append(dcount)
            if ichunk:
                if not isinstance(name, bytes):
                    name = name.encode('utf-8')
                ichunk.write(decint(len(name)))
                ichunk.write(name)
                ichunk.write(decint(cid))
        if ichunk:
            rem = DCHUNK_SIZE - (ichunk.tell() + 16)
            pad = rem - 2
            ichunk = b''.join([b'AOLI', pack('<IQ', rem, len(dchunks)),
                ichunk.getvalue(), (b'\0' * pad), pack('<H', len(dchunks))])
        return dcounts, dchunks, ichunk
