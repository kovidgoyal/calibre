'''
Write content to Mobipocket books.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.cam> and \
        Kovid Goyal <kovid@kovidgoyal.net>'

from collections import defaultdict
from itertools import count
from itertools import izip
import random
import re
from struct import pack
import time
from urlparse import urldefrag

from PIL import Image
from cStringIO import StringIO
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.ebooks.mobi.mobiml import MBP_NS
from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
from calibre.ebooks.oeb.base import XHTML
from calibre.ebooks.oeb.base import XHTML_NS
from calibre.ebooks.oeb.base import XML_NS
from calibre.ebooks.oeb.base import namespace
from calibre.ebooks.oeb.base import prefixname
from calibre.ebooks.oeb.base import urlnormalize
from calibre.ebooks.compression.palmdoc import compress_doc

INDEXING = True

# TODO:
# - Optionally rasterize tables

EXTH_CODES = {
    'creator': 100,
    'publisher': 101,
    'description': 103,
    'identifier': 104,
    'subject': 105,
    'date': 106,
    'review': 107,
    'contributor': 108,
    'rights': 109,
    'type': 111,
    'source': 112,
    'title': 503,
    }

RECORD_SIZE = 0x1000

UNCOMPRESSED = 1
PALMDOC = 2
HUFFDIC = 17480

PALM_MAX_IMAGE_SIZE = 63 * 1024
OTHER_MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_THUMB_SIZE = 16 * 1024
MAX_THUMB_DIMEN = (180, 240)


TAGX = {
        'chapter' :
        '\x00\x00\x00\x01\x01\x01\x01\x00\x02\x01\x02\x00\x03\x01\x04\x00\x04\x01\x08\x00\x00\x00\x00\x01',
        'subchapter' :
        '\x00\x00\x00\x01\x01\x01\x01\x00\x02\x01\x02\x00\x03\x01\x04\x00\x04\x01\x08\x00\x05\x01\x10\x00\x15\x01\x10\x00\x16\x01\x20\x00\x17\x01\x40\x00\x00\x00\x00\x01',
        'periodical' :
        '\x00\x00\x00\x02\x01\x01\x01\x00\x02\x01\x02\x00\x03\x01\x04\x00\x04\x01\x08\x00\x05\x01\x10\x00\x15\x01\x20\x00\x16\x01\x40\x00\x17\x01\x80\x00\x00\x00\x00\x01\x45\x01\x01\x00\x46\x01\x02\x00\x47\x01\x04\x00\x00\x00\x00\x01',
        'secondary_book':'\x00\x00\x00\x01\x01\x01\x01\x00\x00\x00\x00\x01',
        'secondary_periodical':'\x00\x00\x00\x01\x01\x01\x01\x00\x0b\x03\x02\x00\x00\x00\x00\x01'
        }

INDXT = {
        'chapter' : '\x0f',
        'subchapter' : '\x1f',
        'article'    : '\x3f',
        'chapter with subchapters': '\x6f',
        'periodical' : '\xdf',
        'section' : '\xff',
        }

def encode(data):
    return data.encode('utf-8')

# Almost like the one for MS LIT, but not quite.
DECINT_FORWARD = 0
DECINT_BACKWARD = 1
def decint(value, direction):
    bytes = []
    while True:
        b = value & 0x7f
        value >>= 7
        bytes.append(b)
        if value == 0:
            break
    if direction == DECINT_FORWARD:
        bytes[0] |= 0x80
    elif direction == DECINT_BACKWARD:
        bytes[-1] |= 0x80
    return ''.join(chr(b) for b in reversed(bytes))


def align_block(raw, multiple=4, pad='\0'):
    extra = len(raw) % multiple
    if extra == 0: return raw
    return raw + pad*(multiple - extra)


def rescale_image(data, maxsizeb, dimen=None):
    image = Image.open(StringIO(data))
    format = image.format
    changed = False
    if image.format not in ('JPEG', 'GIF'):
        width, height = image.size
        area = width * height
        if area <= 40000:
            format = 'GIF'
        else:
            image = image.convert('RGBA')
            format = 'JPEG'
        changed = True
    if dimen is not None:
        image.thumbnail(dimen, Image.ANTIALIAS)
        changed = True
    if changed:
        data = StringIO()
        image.save(data, format)
        data = data.getvalue()
    if len(data) <= maxsizeb:
        return data
    image = image.convert('RGBA')
    for quality in xrange(95, -1, -1):
        data = StringIO()
        image.save(data, 'JPEG', quality=quality)
        data = data.getvalue()
        if len(data) <= maxsizeb:
            return data
    width, height = image.size
    for scale in xrange(99, 0, -1):
        scale = scale / 100.
        data = StringIO()
        scaled = image.copy()
        size = (int(width * scale), (height * scale))
        scaled.thumbnail(size, Image.ANTIALIAS)
        scaled.save(data, 'JPEG', quality=0)
        data = data.getvalue()
        if len(data) <= maxsizeb:
            return data
    # Well, we tried?
    return data


class Serializer(object):
    NSRMAP = {'': None, XML_NS: 'xml', XHTML_NS: '', MBP_NS: 'mbp'}

    def __init__(self, oeb, images):
        self.oeb = oeb
        self.images = images
        self.logger = oeb.logger
        self.id_offsets = {}
        self.href_offsets = defaultdict(list)
        self.breaks = []
        buffer = self.buffer = StringIO()
        buffer.write('<html>')
        self.serialize_head()
        self.serialize_body()
        buffer.write('</html>')
        self.fixup_links()
        self.text = buffer.getvalue()

    def serialize_head(self):
        buffer = self.buffer
        buffer.write('<head>')
        if len(self.oeb.guide) > 0:
            self.serialize_guide()
        buffer.write('</head>')

    def serialize_guide(self):
        buffer = self.buffer
        hrefs = self.oeb.manifest.hrefs
        buffer.write('<guide>')
        for ref in self.oeb.guide.values():
            path = urldefrag(ref.href)[0]
            if hrefs[path].media_type not in OEB_DOCS:
                continue
            buffer.write('<reference type="')
            self.serialize_text(ref.type, quot=True)
            buffer.write('" ')
            if ref.title is not None:
                buffer.write('title="')
                self.serialize_text(ref.title, quot=True)
                buffer.write('" ')
            self.serialize_href(ref.href)
            # Space required or won't work, I kid you not
            buffer.write(' />')
        buffer.write('</guide>')

    def serialize_href(self, href, base=None):
        hrefs = self.oeb.manifest.hrefs
        path, frag = urldefrag(urlnormalize(href))
        if path and base:
            path = base.abshref(path)
        if path and path not in hrefs:
            return False
        buffer = self.buffer
        item = hrefs[path] if path else None
        if item and item.spine_position is None:
            return False
        path = item.href if item else base.href
        href = '#'.join((path, frag)) if frag else path
        buffer.write('filepos=')
        self.href_offsets[href].append(buffer.tell())
        buffer.write('0000000000')
        return True

    def serialize_body(self):
        buffer = self.buffer
        self.anchor_offset = buffer.tell()
        buffer.write('<body>')
        # CybookG3 'Start Reading' link
        if 'text' in self.oeb.guide:
            href = self.oeb.guide['text'].href
            buffer.write('<a ')
            self.serialize_href(href)
            buffer.write(' />')
        spine = [item for item in self.oeb.spine if item.linear]
        spine.extend([item for item in self.oeb.spine if not item.linear])
        for item in spine:
            self.serialize_item(item)
        buffer.write('</body>')

    def serialize_item(self, item):
        buffer = self.buffer
        if not item.linear:
            self.breaks.append(buffer.tell() - 1)
        self.id_offsets[item.href] = buffer.tell()
        for elem in item.data.find(XHTML('body')):
            self.serialize_elem(elem, item)
        buffer.write('<mbp:pagebreak/>')

    def serialize_elem(self, elem, item, nsrmap=NSRMAP):
        buffer = self.buffer
        if not isinstance(elem.tag, basestring) \
            or namespace(elem.tag) not in nsrmap:
                return
        tag = prefixname(elem.tag, nsrmap)
        # Previous layers take care of @name
        id = elem.attrib.pop('id', None)
        if id is not None:
            href = '#'.join((item.href, id))
            offset = self.anchor_offset or buffer.tell()
            self.id_offsets[href] = offset
        if self.anchor_offset is not None and \
            tag == 'a' and not elem.attrib and \
            not len(elem) and not elem.text:
                return
        self.anchor_offset = buffer.tell()
        buffer.write('<')
        buffer.write(tag)
        if elem.attrib:
            for attr, val in elem.attrib.items():
                if namespace(attr) not in nsrmap:
                    continue
                attr = prefixname(attr, nsrmap)
                buffer.write(' ')
                if attr == 'href':
                    if self.serialize_href(val, item):
                        continue
                elif attr == 'src':
                    href = item.abshref(val)
                    if href in self.images:
                        index = self.images[href]
                        buffer.write('recindex="%05d"' % index)
                        continue
                buffer.write(attr)
                buffer.write('="')
                self.serialize_text(val, quot=True)
                buffer.write('"')
        if elem.text or len(elem) > 0:
            buffer.write('>')
            if elem.text:
                self.anchor_offset = None
                self.serialize_text(elem.text)
            for child in elem:
                self.serialize_elem(child, item)
                if child.tail:
                    self.anchor_offset = None
                    self.serialize_text(child.tail)
            buffer.write('</%s>' % tag)
        else:
            buffer.write('/>')

    def serialize_text(self, text, quot=False):
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        if quot:
            text = text.replace('"', '&quot;')
        self.buffer.write(encode(text))

    def fixup_links(self):
        buffer = self.buffer
        id_offsets = self.id_offsets
        for href, hoffs in self.href_offsets.items():
            if href not in id_offsets:
                self.logger.warn('Hyperlink target %r not found' % href)
                href, _ = urldefrag(href)
            ioff = self.id_offsets[href]
            for hoff in hoffs:
                buffer.seek(hoff)
                buffer.write('%010d' % ioff)



class MobiWriter(object):
    COLLAPSE_RE = re.compile(r'[ \t\r\n\v]+')

    def __init__(self, opts, compression=PALMDOC, imagemax=None,
            prefer_author_sort=False):
        self.opts = opts
        self._compression = compression or UNCOMPRESSED
        self._imagemax = imagemax or OTHER_MAX_IMAGE_SIZE
        self._prefer_author_sort = prefer_author_sort
        self._primary_index_record = None

    @classmethod
    def generate(cls, opts):
        """Generate a Writer instance from command-line options."""
        imagemax = PALM_MAX_IMAGE_SIZE if opts.rescale_images else None
        prefer_author_sort = opts.prefer_author_sort
        return cls(compression=PALMDOC, imagemax=imagemax,
            prefer_author_sort=prefer_author_sort)

    def __call__(self, oeb, path):
        if hasattr(path, 'write'):
            return self._dump_stream(oeb, path)
        with open(path, 'w+b') as stream:
            return self._dump_stream(oeb, stream)

    def _write(self, * data):
        for datum in data:
            self._stream.write(datum)

    def _tell(self):
        return self._stream.tell()

    def _dump_stream(self, oeb, stream):
        self._oeb = oeb
        self._stream = stream
        self._records = [None]
        self._generate_content()
        self._generate_record0()
        self._write_header()
        self._write_content()

    def _generate_content(self):
        self._map_image_names()
        self._generate_text()
        if INDEXING and not self.opts.no_mobi_index:
            try:
                self._generate_index()
            except:
                self._oeb.log.exception('Failed to generate index')
        self._generate_images()

    def _map_image_names(self):
        index = 1
        self._images = images = {}
        for item in self._oeb.manifest.values():
            if item.media_type in OEB_RASTER_IMAGES:
                images[item.href] = index
                index += 1

    def _read_text_record(self, text):
        pos = text.tell()
        text.seek(0, 2)
        npos = min((pos + RECORD_SIZE, text.tell()))
        last = ''
        while not last.decode('utf-8', 'ignore'):
            size = len(last) + 1
            text.seek(npos - size)
            last = text.read(size)
        extra = 0
        try:
            last.decode('utf-8')
        except UnicodeDecodeError:
            prev = len(last)
            while True:
                text.seek(npos - prev)
                last = text.read(len(last) + 1)
                try:
                    last.decode('utf-8')
                except UnicodeDecodeError:
                    pass
                else:
                    break
            extra = len(last) - prev
        text.seek(pos)
        data = text.read(RECORD_SIZE)
        overlap = text.read(extra)
        text.seek(npos)
        return data, overlap

    def _generate_text(self):
        self._oeb.logger.info('Serializing markup content...')
        serializer = Serializer(self._oeb, self._images)
        breaks = serializer.breaks
        text = serializer.text
        self._id_offsets = serializer.id_offsets
        self._content_length = len(text)
        self._text_length = len(text)
        text = StringIO(text)
        buf = []
        nrecords = 0
        offset = 0
        if self._compression != UNCOMPRESSED:
            self._oeb.logger.info('Compressing markup content...')
        data, overlap = self._read_text_record(text)
        while len(data) > 0:
            if self._compression == PALMDOC:
                data = compress_doc(data)
            record = StringIO()
            record.write(data)
            record.write(overlap)
            record.write(pack('>B', len(overlap)))
            nextra = 0
            pbreak = 0
            running = offset
            while breaks and (breaks[0] - offset) < RECORD_SIZE:
                pbreak = (breaks.pop(0) - running) >> 3
                encoded = decint(pbreak, DECINT_FORWARD)
                record.write(encoded)
                running += pbreak << 3
                nextra += len(encoded)
            lsize = 1
            while True:
                size = decint(nextra + lsize, DECINT_BACKWARD)
                if len(size) == lsize:
                    break
                lsize += 1
            record.write(size)
            self._records.append(record.getvalue())
            buf.append(self._records[-1])
            nrecords += 1
            offset += RECORD_SIZE
            data, overlap = self._read_text_record(text)
        if INDEXING:
            extra = sum(map(len, buf))%4
            if extra == 0:
                extra = 4
            self._records.append('\0'*(4-extra))
            nrecords += 1
        self._text_nrecords = nrecords

    def _generate_indxt(self, ctoc):
        if self.opts.mobi_periodical:
            raise NotImplementedError('Indexing for periodicals not implemented')
        toc = self._oeb.toc
        indxt, indices, c = StringIO(), StringIO(), 0

        indices.write('IDXT')
        c = 0
        last_name = None

        def add_node(node, offset, length, count):
            if self.opts.verbose > 2:
                self._oeb.log.debug('Adding TOC node:', node.title, 'href:',
                        node.href)

            pos = 0xc0 + indxt.tell()
            indices.write(pack('>H', pos))
            name = "%4d"%count
            indxt.write(chr(len(name)) + name)
            indxt.write(INDXT['chapter'])
            indxt.write(decint(offset, DECINT_FORWARD))
            indxt.write(decint(length, DECINT_FORWARD))
            indxt.write(decint(self._ctoc_map[node], DECINT_FORWARD))
            indxt.write(decint(0, DECINT_FORWARD))


        entries = list(toc.iter())[1:]
        for i, child in enumerate(entries):
            if not child.title or not child.title.strip():
                continue
            h = child.href
            if h not in self._id_offsets:
                self._oeb.log.warning('Could not find TOC entry:', child.title)
                continue
            offset = self._id_offsets[h]
            length = None
            for sibling in entries[i+1:]:
                h2 = sibling.href
                if h2 in self._id_offsets:
                    offset2 = self._id_offsets[h2]
                    if offset2 > offset:
                        length = offset2 - offset
                        break
            if length is None:
                length = self._content_length - offset

            add_node(child, offset, length, c)
            ctoc_offset = self._ctoc_map[child]
            last_name = "%4d"%c
            c += 1

        return align_block(indxt.getvalue()), c, \
            align_block(indices.getvalue()), last_name


    def _generate_index(self):
        self._oeb.log('Generating index...')
        self._primary_index_record = None
        ctoc = self._generate_ctoc()
        indxt, indxt_count, indices, last_name = \
                self._generate_indxt(ctoc)
        if last_name is None:
            self._oeb.log.warn('Input document has no TOC. No index generated.')
            return

        indx1 = StringIO()
        indx1.write('INDX'+pack('>I', 0xc0)) # header length

        # 0x8 - 0xb : Unknown
        indx1.write('\0'*4)

        # 0xc - 0xf : Header type
        indx1.write(pack('>I', 1))

        # 0x10 - 0x13 : Unknown
        indx1.write('\0'*4)

        # 0x14 - 0x17 : IDXT offset
        # 0x18 - 0x1b : IDXT count
        indx1.write(pack('>I', 0xc0+len(indxt)))
        indx1.write(pack('>I', indxt_count))

        # 0x1c - 0x23 : Unknown
        indx1.write('\xff'*8)

        # 0x24 - 0xbf
        indx1.write('\0'*156)
        indx1.write(indxt)
        indx1.write(indices)
        indx1 = indx1.getvalue()

        idxt0 = chr(len(last_name)) + last_name + pack('>H', indxt_count)
        idxt0 = align_block(idxt0)
        indx0 = StringIO()

        tagx = TAGX['periodical' if self.opts.mobi_periodical else 'chapter']
        tagx = align_block('TAGX' + pack('>I', 8 + len(tagx)) + tagx)
        indx0_indices_pos = 0xc0 + len(tagx) + len(idxt0)
        indx0_indices = align_block('IDXT' + pack('>H', 0xc0 + len(tagx)))
        # Generate record header
        header = StringIO()

        header.write('INDX')
        header.write(pack('>I', 0xc0)) # header length

        # 0x08 - 0x0b : Unknown
        header.write('\0'*4)

        # 0x0c - 0x0f : Header type
        header.write(pack('>I', 0))

        # 0x10 - 0x13 : Generator ID
        header.write(pack('>I', 6))

        # 0x14 - 0x17 : IDXT offset
        header.write(pack('>I', indx0_indices_pos))

        # 0x18 - 0x1b : IDXT count
        header.write(pack('>I', 1))

        # 0x1c - 0x1f : Text encoding ?
        header.write(pack('>I', 650001))

        # 0x20 - 0x23 : Language code?
        header.write(iana2mobi(str(self._oeb.metadata.language[0])))

        # 0x24 - 0x27 : Number of TOC entries in INDX1
        header.write(pack('>I', indxt_count))

        # 0x28 - 0x2b : ORDT Offset
        header.write('\0'*4)

        # 0x2c - 0x2f : LIGT offset
        header.write('\0'*4)

        # 0x30 - 0x33 : Number of LIGT entries
        header.write('\0'*4)

        # 0x34 - 0x37 : Unknown
        header.write(pack('>I', 1))

        # 0x38 - 0xb3 : Unknown (pad?)
        header.write('\0'*124)

        # 0xb4 - 0xb7 : TAGX offset
        header.write(pack('>I', 0xc0))

        # 0xb8 - 0xbf : Unknown
        header.write('\0'*8)

        header = header.getvalue()

        indx0.write(header)
        indx0.write(tagx)
        indx0.write(idxt0)
        indx0.write(indx0_indices)
        indx0 = indx0.getvalue()

        self._primary_index_record = len(self._records)
        self._records.extend([indx0, indx1, ctoc])

        # Write secondary index records
        tagx = TAGX['secondary_'+\
                ('periodical' if self.opts.mobi_periodical else 'book')]
        tagx_len = 8 + len(tagx)

        indx0 = StringIO()
        indx0.write('INDX'+pack('>I', 0xc0)+'\0'*8)
        indx0.write(pack('>I', 0x02))
        indx0.write(pack('>I', 0xc0+tagx_len+4))
        indx0.write(pack('>I', 1))
        indx0.write(pack('>I', 65001))
        indx0.write('\xff'*4)
        indx0.write(pack('>I', 1))
        indx0.write('\0'*4)
        indx0.write('\0'*136)
        indx0.write(pack('>I', 0xc0))
        indx0.write('\0'*8)
        indx0.write('TAGX'+pack('>I', tagx_len)+tagx)
        if self.opts.mobi_periodical:
            raise NotImplementedError
        else:
            indx0.write('\0'*3 + '\x01' + 'IDXT' + '\0\xd4\0\0')
        indx1 = StringIO()
        indx1.write('INDX' + pack('>I', 0xc0) + '\0'*4)
        indx1.write(pack('>I', 1))
        extra = 0xf0 if self.opts.mobi_periodical else 4
        indx1.write('\0'*4 + pack('>I', 0xc0+extra))
        num = 4 if self.opts.mobi_periodical else 1
        indx1.write(pack('>I', num))
        indx1.write('\xff'*8)
        indx1.write('\0'*(0xc0-indx1.tell()))
        if self.opts.mobi_periodical:
            raise NotImplementedError
        else:
            indx1.write('\0\x01\x80\0')
        indx1.write('IDXT')
        if self.opts.mobi_periodical:
            raise NotImplementedError
        else:
            indx1.write('\0\xc0\0\0')

        indx0, indx1 = indx0.getvalue(), indx1.getvalue()
        self._records.extend((indx0, indx1))
        if self.opts.verbose > 3:
            from tempfile import mkdtemp
            import os
            t = mkdtemp()
            for i, n in enumerate(['sindx1', 'sindx0', 'ctoc', 'indx0', 'indx1']):
                open(os.path.join(t, n+'.bin'), 'wb').write(self._records[-(i+1)])
            self._oeb.log.debug('Index records dumped to', t)




    def _generate_ctoc(self):
        if self.opts.mobi_periodical:
            raise NotImplementedError('Indexing for periodicals not implemented')
        toc = self._oeb.toc
        self._ctoc_map = {}
        self._ctoc_name_map = {}
        self._last_toc_entry = None
        ctoc = StringIO()

        def add_node(node, cls, title=None):
            t = node.title if title is None else title
            if t and t.strip():
                t = t.strip()
                if not isinstance(t, unicode):
                    t = t.decode('utf-8', 'replace')
                t = t.encode('utf-8')
                self._last_toc_entry = t
                self._ctoc_map[node] = ctoc.tell()
                self._ctoc_name_map[node] = t
                ctoc.write(decint(len(t), DECINT_FORWARD)+t)

        first = True
        for child in toc.iter():
            add_node(child, 'chapter')#, title='Title Page' if first else None)
            first = False

        return align_block(ctoc.getvalue())

    def _generate_images(self):
        self._oeb.logger.info('Serializing images...')
        images = [(index, href) for href, index in self._images.items()]
        images.sort()
        self._first_image_record = None
        for _, href in images:
            item = self._oeb.manifest.hrefs[href]
            try:
                data = rescale_image(item.data, self._imagemax)
            except IOError:
                self._oeb.logger.warn('Bad image file %r' % item.href)
                continue
            self._records.append(data)
            if self._first_image_record is None:
                self._first_image_record = len(self._records)-1

    def _generate_end_records(self):
        self._flis_number = len(self._records)
        self._records.append(
        'FLIS\0\0\0\x08\0\x41\0\0\0\0\0\0\xff\xff\xff\xff\0\x01\0\x03\0\0\0\x03\0\0\0\x01'+
        '\xff'*4)
        fcis = 'FCIS\x00\x00\x00\x14\x00\x00\x00\x10\x00\x00\x00\x01\x00\x00\x00\x00'
        fcis += pack('>I', self._text_length)
        fcis += '\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00\x08\x00\x01\x00\x01\x00\x00\x00\x00'
        self._fcis_number = len(self._records)
        self._records.append(fcis)
        self._records.append('\xE9\x8E\x0D\x0A')

    def _generate_record0(self):
        metadata = self._oeb.metadata
        exth = self._build_exth()
        last_content_record = len(self._records) - 1
        if INDEXING:
            self._generate_end_records()
        record0 = StringIO()
        # The PalmDOC Header
        record0.write(pack('>HHIHHHH', self._compression, 0,
            self._text_length,
            self._text_nrecords, RECORD_SIZE, 0, 0)) # 0 - 15 (0x0 - 0xf)
        uid = random.randint(0, 0xffffffff)
        title = str(metadata.title[0])
        # The MOBI Header

        # 0x0 - 0x3
        record0.write('MOBI')

        # 0x4 - 0x7   : Length of header
        # 0x8 - 0x11  : MOBI type
        #   type    meaning
        #   0x002   MOBI book (chapter - chapter navigation)
        #   0x101   News - Hierarchical navigation with sections and articles
        #   0x102   News feed - Flat navigation
        #   0x103   News magazine - same as 1x101
        # 0xC - 0xF   : Text encoding (65001 is utf-8)
        # 0x10 - 0x13 : UID
        # 0x14 - 0x17 : Generator version
        btype = 0x101 if self.opts.mobi_periodical else 2
        record0.write(pack('>IIIII',
            0xe8, btype, 65001, uid, 6))

        # 0x18 - 0x1f : Unknown
        record0.write('\xff' * 8)

        # 0x20 - 0x23 : Secondary index record
        record0.write(pack('>I', 0xffffffff if self._primary_index_record is
            None else self._primary_index_record+3))

        # 0x24 - 0x3f : Unknown
        record0.write('\xff' * 28)

        # 0x40 - 0x43 : Offset of first non-text record
        record0.write(pack('>I',
            self._text_nrecords + 1))

        # 0x44 - 0x4b : title offset, title length
        record0.write(pack('>II',
            0xe8 + 16 + len(exth), len(title)))

        # 0x4c - 0x4f : Language specifier
        record0.write(iana2mobi(
            str(metadata.language[0])))

        # 0x50 - 0x57 : Unknown
        record0.write('\0' * 8)

        # 0x58 - 0x5b : Format version
        # 0x5c - 0x5f : First image record number
        record0.write(pack('>II',
            6, self._first_image_record if self._first_image_record else 0))

        # 0x60 - 0x63 : First HUFF/CDIC record number
        # 0x64 - 0x67 : Number of HUFF/CDIC records
        # 0x68 - 0x6b : First DATP record number
        # 0x6c - 0x6f : Number of DATP records
        record0.write('\0' * 16)

        # 0x70 - 0x73 : EXTH flags
        record0.write(pack('>I', 0x50))

        # 0x74 - 0x93 : Unknown
        record0.write('\0' * 32)

        # 0x94 - 0x97 : DRM offset
        # 0x98 - 0x9b : DRM count
        # 0x9c - 0x9f : DRM size
        # 0xa0 - 0xa3 : DRM flags
        record0.write(pack('>IIII',
            0xffffffff, 0xffffffff, 0, 0))


        # 0xa4 - 0xaf : Unknown
        record0.write('\0'*12)

        # 0xb0 - 0xb1 : First content record number
        # 0xb2 - 0xb3 : last content record number
        # (Includes Image, DATP, HUFF, DRM)
        record0.write(pack('>HH', 1, last_content_record))

        # 0xb4 - 0xb7 : Unknown
        record0.write('\0\0\0\x01')

        # 0xb8 - 0xbb : FCIS record number
        record0.write(pack('>I', self._fcis_number))

        # 0xbc - 0xbf : Unknown (FCIS record count?)
        record0.write(pack('>I', 1))

        # 0xc0 - 0xc3 : FLIS record number
        record0.write(pack('>I', self._flis_number))

        # 0xc4 - 0xc7 : Unknown (FLIS record count?)
        record0.write(pack('>I', 1))

        # 0xc8 - 0xcf : Unknown
        record0.write('\0'*8)

        # 0xd0 - 0xdf : Unknown
        record0.write(pack('>IIII', 0xffffffff, 0, 0xffffffff, 0xffffffff))

        # 0xe0 - 0xe3 : Extra record data
        # The '5' is a bitmask of extra record data at the end:
        #   - 0x1: <extra multibyte bytes><size> (?)
        #   - 0x4: <uncrossable breaks><size>
        # Of course, the formats aren't quite the same.
        record0.write(pack('>I', 5))

        # 0xe4 - 0xe7 : Primary index record
        record0.write(pack('>I', 0xffffffff if self._primary_index_record is
            None else self._primary_index_record))

        record0.write(exth)
        record0.write(title)
        record0 = record0.getvalue()
        self._records[0] = record0 + ('\0' * (2452 - len(record0)))

    def _build_exth(self):
        oeb = self._oeb
        exth = StringIO()
        nrecs = 0
        for term in oeb.metadata:
            if term not in EXTH_CODES: continue
            code = EXTH_CODES[term]
            items = oeb.metadata[term]
            if term == 'creator':
                if self._prefer_author_sort:
                    creators = [unicode(c.file_as or c) for c in items]
                else:
                    creators = [unicode(c) for c in items]
                items = ['; '.join(creators)]
            for item in items:
                data = self.COLLAPSE_RE.sub(' ', unicode(item))
                if term == 'identifier':
                    if data.lower().startswith('urn:isbn:'):
                        data = data[9:]
                    elif item.scheme.lower() == 'isbn':
                        pass
                    else:
                        continue
                data = data.encode('utf-8')
                exth.write(pack('>II', code, len(data) + 8))
                exth.write(data)
                nrecs += 1
        if oeb.metadata.cover:
            id = str(oeb.metadata.cover[0])
            item = oeb.manifest.ids[id]
            href = item.href
            index = self._images[href] - 1
            exth.write(pack('>III', 0xc9, 0x0c, index))
            exth.write(pack('>III', 0xcb, 0x0c, 0))
            nrecs += 2
            index = self._add_thumbnail(item)
            if index is not None:
                exth.write(pack('>III', 0xca, 0x0c, index - 1))
                nrecs += 1
        if INDEXING:
            # Write unknown EXTH records as 0s
            for code, size in [(204,4), (205,4), (206,4), (207,4), (300,40)]:
                exth.write(pack('>II', code, 8+size)+'\0'*size)
                nrecs += 1
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ['EXTH', pack('>II', len(exth) + 12, nrecs), exth, pad]
        return ''.join(exth)

    def _add_thumbnail(self, item):
        try:
            data = rescale_image(item.data, MAX_THUMB_SIZE, MAX_THUMB_DIMEN)
        except IOError:
            self._oeb.logger.warn('Bad image file %r' % item.href)
            return None
        manifest = self._oeb.manifest
        id, href = manifest.generate('thumbnail', 'thumbnail.jpeg')
        manifest.add(id, href, 'image/jpeg', data=data)
        index = len(self._images) + 1
        self._images[href] = index
        self._records.append(data)
        return index

    def _write_header(self):
        title = str(self._oeb.metadata.title[0])
        title = re.sub('[^-A-Za-z0-9]+', '_', title)[:31]
        title = title + ('\0' * (32 - len(title)))
        now = int(time.time())
        nrecords = len(self._records)
        self._write(title, pack('>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0),
            'BOOK', 'MOBI', pack('>IIH', nrecords, 0, nrecords))
        offset = self._tell() + (8 * nrecords) + 2
        for id, record in izip(count(), self._records):
            self._write(pack('>I', offset), '\0', pack('>I', id)[1:])
            offset += len(record)
        self._write('\0\0')

    def _write_content(self):
        for record in self._records:
            self._write(record)


