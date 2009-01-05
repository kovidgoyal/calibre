'''
Write content to Mobipocket books.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.cam>'

import sys
import os
from struct import pack
import functools
import time
import random
from cStringIO import StringIO
import re
from itertools import izip, count
from collections import defaultdict
from urlparse import urldefrag
from lxml import etree
from PIL import Image
from calibre.ebooks.oeb.base import XML_NS, XHTML, XHTML_NS, OEB_DOCS, \
    OEB_RASTER_IMAGES
from calibre.ebooks.oeb.base import xpath, barename, namespace, prefixname
from calibre.ebooks.oeb.base import FauxLogger, OEBBook
from calibre.ebooks.oeb.profile import Context
from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
from calibre.ebooks.mobi.palmdoc import compress_doc
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.ebooks.mobi.mobiml import MBP_NS, MBP, MobiMLizer

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

def encode(data):
    return data.encode('utf-8')

# Almost like the one for MS LIT, but not quite.
def decint(value):
    bytes = []
    while True:
        b = value & 0x7f
        value >>= 7
        if not bytes:
            b |= 0x80
        bytes.append(chr(b))
        if value == 0:
            break
    return ''.join(reversed(bytes))


class Serializer(object):
    NSRMAP = {'': None, XML_NS: 'xml', XHTML_NS: '', MBP_NS: 'mbp'}
    
    def __init__(self, oeb, images):
        self.oeb = oeb
        self.images = images
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
            path, frag = urldefrag(ref.href)
            if hrefs[path].media_type not in OEB_DOCS:
                continue
            buffer.write('<reference title="%s" type="%s" '
                         % (ref.title, ref.type))
            self.serialize_href(ref.href)
            buffer.write(' />')
        buffer.write('</guide>')

    def serialize_href(self, href, base=None):
        hrefs = self.oeb.manifest.hrefs
        path, frag = urldefrag(href)
        if path and base:
            path = base.abshref(path)
        if path and path not in hrefs:
            return False
        buffer = self.buffer
        item = hrefs[path] if path else None
        if item and item.spine_position is None:
            return False
        id =  item.id if item else base.id
        frag = frag if frag else 'calibre_top'
        href = '#'.join((id, frag))
        buffer.write('filepos=')
        self.href_offsets[href].append(buffer.tell())
        buffer.write('0000000000')
        return True
        
    def serialize_body(self):
        buffer = self.buffer
        buffer.write('<body>')
        spine = [item for item in self.oeb.spine if item.linear]
        spine.extend([item for item in self.oeb.spine if not item.linear])
        for item in spine:
            self.serialize_item(item)
        buffer.write('</body>')

    def serialize_item(self, item):
        buffer = self.buffer
        if not item.linear:
            self.breaks.append(buffer.tell() - 1)
        self.id_offsets[item.id + '#calibre_top'] = buffer.tell()
        for elem in item.data.find(XHTML('body')):
            self.serialize_elem(elem, item)
        buffer.write(' <mbp:pagebreak/>')

    def serialize_elem(self, elem, item, nsrmap=NSRMAP):
        buffer = self.buffer
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) not in nsrmap:
            return
        hrefs = self.oeb.manifest.hrefs
        tag = prefixname(elem.tag, nsrmap)
        for attr in ('name', 'id'):
            if attr in elem.attrib:
                id = '#'.join((item.id, elem.attrib[attr]))
                self.id_offsets[id] = buffer.tell()
                del elem.attrib[attr]
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
                elif attr == 'src' and val in hrefs:
                    index = self.images[val]
                    buffer.write('recindex="%05d"' % index)
                    continue
                buffer.write(attr)
                buffer.write('="')
                self.serialize_text(val, quot=True)
                buffer.write('"')
        if elem.text or len(elem) > 0:
            buffer.write('>')
            if elem.text:
                self.serialize_text(elem.text)
            for child in elem:
                self.serialize_elem(child, item)
                if child.tail:
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
        for id, hoffs in self.href_offsets.items():
            ioff = self.id_offsets[id]
            for hoff in hoffs:
                buffer.seek(hoff)
                buffer.write('%010d' % ioff)

    
class MobiWriter(object):
    def __init__(self, compression=None, logger=FauxLogger()):
        self._compression = compression or UNCOMPRESSED
        self._logger = logger

    def dump(self, oeb, path):
        if hasattr(path, 'write'):
            return self._dump_stream(oeb, path)
        with open(path, 'w+b') as stream:
            return self._dump_stream(oeb, stream)
    
    def _write(self, *data):
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
        try:
            last.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            text.seek(pos)
            return text.read(RECORD_SIZE)
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
        data = text.read(RECORD_SIZE + extra)
        text.seek(npos)
        return data
                
    def _generate_text(self):
        serializer = Serializer(self._oeb, self._images)
        breaks = serializer.breaks
        text = serializer.text
        self._text_length = len(text)
        text = StringIO(text)
        nrecords = 0
        offset = 0
        data = self._read_text_record(text)
        while len(data) > 0:
            size = len(data)
            if self._compression == PALMDOC:
                data = compress_doc(data)
            record = StringIO()
            record.write(data)
            record.write(pack('>B', max((0, size - RECORD_SIZE))))
            nextra = 0
            pbreak = 0
            running = offset
            while breaks and (breaks[0] - offset) < RECORD_SIZE:
                pbreak = (breaks.pop(0) - running) >> 3
                encoded = decint(pbreak)
                record.write(encoded)
                running += pbreak << 3
                nextra += len(encoded)
            record.write(decint(nextra + 1))
            self._records.append(record.getvalue())
            nrecords += 1
            offset += RECORD_SIZE
            data = self._read_text_record(text)
        self._text_nrecords = nrecords

    def _rescale_image(self, data, maxsizeb, dimen=None):
        image = Image.open(StringIO(data))
        format = image.format
        changed = False
        if image.format not in ('JPEG', 'GIF', 'PNG'):
            format = 'PNG'
            changed = True
        if dimen is not None:
            image.thumbnail(dimen, Image.ANTIALIAS)
            changed = True
        if changed:
            data = StringIO()
            image.save(data, format)
            data = data.getvalue()
        if len(data) < maxsizeb:
            return data
        image = image.convert('RGBA')
        for quality in xrange(95, -1, -1):
            data = StringIO()
            image.save(data, 'JPEG', quality=quality)
            data = data.getvalue()
            if len(data) <= maxsizeb:
                break
        return data
        
    def _generate_images(self):
        images = [(index, href) for href, index in self._images.items()]
        images.sort()
        metadata = self._oeb.metadata
        coverid = metadata.cover[0] if metadata.cover else None
        for _, href in images:
            item = self._oeb.manifest.hrefs[href]
            maxsizek = 89 if coverid == item.id else 63
            maxsizeb = maxsizek * 1024
            data = self._rescale_image(item.data, maxsizeb)
            self._records.append(data)
    
    def _generate_record0(self):
        metadata = self._oeb.metadata
        exth = self._build_exth()
        record0 = StringIO()
        record0.write(pack('>HHIHHHH', self._compression, 0,
            self._text_length, self._text_nrecords, RECORD_SIZE, 0, 0))
        uid = random.randint(0, 0xffffffff)
        title = str(metadata.title[0])
        record0.write('MOBI')
        record0.write(pack('>IIIII', 0xe8, 2, 65001, uid, 6))
        record0.write('\xff' * 40)
        record0.write(pack('>I', self._text_nrecords + 1))
        record0.write(pack('>II', 0xe8 + 16 + len(exth), len(title)))
        record0.write(iana2mobi(str(metadata.language[0])))
        record0.write('\0' * 8)
        record0.write(pack('>II', 6, self._text_nrecords + 1))
        record0.write('\0' * 16)
        record0.write(pack('>I', 0x50))
        record0.write('\0' * 32)
        record0.write(pack('>IIII', 0xffffffff, 0xffffffff, 0, 0))
        # The '5' is a bitmask of extra record data at the end:
        #   - 0x1: <extra multibyte bytes><size> (?)
        #   - 0x4: <uncrossable breaks><size>
        # Of course, the formats aren't quite the same.
        # TODO: What the hell are the rest of these fields?
        record0.write(pack('>IIIIIIIIIIIIIIIII',
            0, 0, 0, 0xffffffff, 0, 0xffffffff, 0, 0xffffffff, 0, 0xffffffff,
            0, 0xffffffff, 0, 0xffffffff, 0xffffffff, 5, 0xffffffff))
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
            for item in oeb.metadata[term]:
                data = str(item)
                exth.write(pack('>II', code, len(data) + 8))
                exth.write(data)
                nrecs += 1
        if oeb.metadata.cover:
            id = str(oeb.metadata.cover[0])
            item = oeb.manifest[id]
            href = item.href
            index = self._images[href] - 1
            exth.write(pack('>III', 0xc9, 0x0c, index))
            exth.write(pack('>III', 0xcb, 0x0c, 0))
            index = self._add_thumbnail(item) - 1
            exth.write(pack('>III', 0xca, 0x0c, index))
            nrecs += 3
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '' if not trail else '\0' * (4 - trail)
        exth = ['EXTH', pack('>II', len(exth) + 12, nrecs), exth, pad]
        return ''.join(exth)

    def _add_thumbnail(self, item):
        maxsizeb = 16 * 1024
        dimen = (180, 240)
        data = self._rescale_image(item.data, maxsizeb, dimen)
        manifest = self._oeb.manifest
        id, href = manifest.generate('thumbnail', 'thumbnail.jpeg')
        manifest.add(id, href, 'image/jpeg', data=data)
        index = len(self._images) + 1
        self._images[href] = index
        self._records.append(data)
        return index
    
    def _write_header(self):
        title = str(self._oeb.metadata.title[0])
        title = re.sub('[^-A-Za-z0-9]+', '_', title)[:32]
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


def main(argv=sys.argv):
    from calibre.ebooks.oeb.base import DirWriter
    inpath, outpath = argv[1:]
    context = Context('Firefox', 'MobiDesktop')
    oeb = OEBBook(inpath)
    #writer = MobiWriter(compression=PALMDOC)
    writer = MobiWriter(compression=UNCOMPRESSED)
    #writer = DirWriter()
    fbase = context.dest.fbase
    fkey = context.dest.fnums.values()
    flattener = CSSFlattener(unfloat=True, fbase=fbase, fkey=fkey)
    rasterizer = SVGRasterizer()
    mobimlizer = MobiMLizer()
    flattener.transform(oeb, context)
    rasterizer.transform(oeb, context)
    mobimlizer.transform(oeb, context)    
    writer.dump(oeb, outpath)
    return 0

if __name__ == '__main__':
    sys.exit(main())
