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
from calibre.ebooks.mobi.palmdoc import compress_doc
from calibre.ebooks.lit.oeb import XHTML, XHTML_NS, OEB_DOCS
from calibre.ebooks.lit.oeb import xpath, barename, namespace
from calibre.ebooks.lit.oeb import FauxLogger, OEBBook

MBP_NS = 'http://mobipocket.cam/ns/mbp'
def MBP(name): return '{%s}%s' % (MBP_NS, name)

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

UNCOMPRESSED = 1
PALMDOC = 2
HUFFDIC = 17480

COLLAPSE = re.compile(r'[ \t\r\n\v]+')

def encode(data):
    return COLLAPSE.sub(' ', data).encode('ascii', 'xmlcharrefreplace')


class Serializer(object):
    def __init__(self, oeb, images):
        self.oeb = oeb
        self.images = images
        self.id_offsets = {}
        self.href_offsets = defaultdict(list)
        buffer = self.buffer = StringIO()
        buffer.write('<html>')
        self.serialize_head()
        self.serialize_body()
        buffer.write('</html>')
        self.fixup_links()
        self.raw = buffer.getvalue()

    def __str__(self):
        return self.raw

    def serialize_head(self):
        buffer = self.buffer
        buffer.write('<head>')
        buffer.write('</head>')
        
    def serialize_body(self):
        buffer = self.buffer
        buffer.write('<body>')
        for item in self.oeb.spine:
            self.serialize_item(item)
        buffer.write('</body>')

    def serialize_item(self, item):
        buffer = self.buffer
        buffer.write('<mbp:pagebreak/>')
        # TODO: Figure out how to make the 'crossable' stuff work for
        # non-"linear" spine items.
        self.id_offsets[item.id + '_calibre_top'] = buffer.tell()
        for elem in item.data.find(XHTML('body')):
            self.serialize_elem(elem, item)

    def serialize_elem(self, elem, item):
        ns = namespace(elem.tag)
        if ns not in (XHTML_NS, MBP_NS):
            return
        buffer = self.buffer
        hrefs = self.oeb.manifest.hrefs
        tag = barename(elem.tag)
        if ns == MBP_NS: tag = 'mbp:' + tag
        for attr in ('name', 'id'):
            if attr in elem.attrib:
                id = '_'.join((item.id, elem.attrib[attr]))
                self.id_offsets[id] = buffer.tell()
                del elem.attrib[attr]
        buffer.write('<')
        buffer.write(tag)
        if elem.attrib:
            for attr, val in elem.attrib.items():
                buffer.write(' ')
                if attr == 'href':
                    path, frag = urldefrag(val)
                    # TODO: Absolute path translation
                    if not path or path in hrefs:
                        id = hrefs[path].id if path else item.id
                        frag = frag if frag else 'calibre_top'
                        href = '_'.join((id, frag))
                        buffer.write('filepos=')
                        self.href_offsets[href].append(buffer.tell())
                        buffer.write('0000000000')
                        continue
                elif attr == 'src' and val in hrefs:
                    index = self.images[val]
                    buffer.write('recindex="%05d"' % index)
                    continue
                buffer.write('%s="%s"' % (attr, val))
        if not elem.text and len(elem) == 0:
            buffer.write('/>')
            return
        buffer.write('>')
        if elem.text:
            buffer.write(encode(elem.text))
        for child in elem:
            self.serialize_elem(child, item)
        buffer.write('</%s>' % tag)
        if elem.tail:
            buffer.write(encode(elem.tail))

    def fixup_links(self):
        buffer = self.buffer
        for id, hoffs in self.href_offsets.items():
            ioff = self.id_offsets[id]
            for hoff in hoffs:
                buffer.seek(hoff)
                buffer.write('%010d' % ioff)

    
def preserve(function):
    def wrapper(self, *args, **kwargs):
        opos = self._stream.tell()
        try:
            return function(self, *args, **kwargs)
        finally:
            self._stream.seek(opos)
    functools.update_wrapper(wrapper, function)
    return wrapper
    
class MobiWriter(object):
    def __init__(self, compress=None, logger=FauxLogger()):
        self._compress = compress or UNCOMPRESSED
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
            if item.media_type.startswith('image/'):
                images[item.href] = index
                index += 1
        
    def _generate_text(self):
        serializer = Serializer(self._oeb, self._images)
        text = str(serializer)
        self._text_length = len(text)
        text = StringIO(text)
        nrecords = 0
        data = text.read(0x1000)
        while len(data) > 0:
            nrecords += 1
            if self._compress == PALMDOC:
                data = compress_doc(data)
            # Without the NUL Mobipocket Desktop 6.2 will thrash.  Why?
            self._records.append(data + '\0')
            data = text.read(0x1000)
        self._text_nrecords = nrecords

    def _generate_images(self):
        images = [(index, href) for href, index in self._images.items()]
        images.sort()
        metadata = self._oeb.metadata
        coverid = metadata.cover[0] if metadata.cover else None
        for _, href in images:
            item = self._oeb.manifest.hrefs[href]
            data = item.data
            # TODO: Re-size etc images
            image = Image.open(StringIO(item.data))
            maxsizek = 89 if coverid == item.id else 63
            maxsizeb = maxsizek * 1024
            for quality in xrange(95, -1, -1):
                data = StringIO()
                image.save(data, 'JPEG', quality=quality)
                data = data.getvalue()
                if len(data) <= maxsizeb:
                    break
            self._records.append(data)
    
    def _generate_record0(self):
        exth = self._build_exth()
        record0 = StringIO()
        record0.write(pack('>HHIHHHH', self._compress, 0, self._text_length,
            self._text_nrecords, 0x1000, 0, 0))
        uid = random.randint(0, 0xffffffff)
        title = str(self._oeb.metadata.title[0])
        record0.write('MOBI')
        record0.write(pack('>IIIII', 0xe8, 2, 65001, uid, 5))
        record0.write('\xff' * 40)
        record0.write(pack('>I', self._text_nrecords + 1))
        record0.write(pack('>II', 0xe8 + 16 + len(exth), len(title)))
        # TODO: Translate <dc:language/> to language code
        record0.write(pack('>I', 9))
        record0.write('\0' * 8)
        record0.write(pack('>II', 5, self._text_nrecords + 1))
        record0.write('\0' * 16)
        record0.write(pack('>I', 0x50))
        record0.write('\0' * 32)
        record0.write(pack('>IIII', 0xffffffff, 0xffffffff, 0, 0))
        # TODO: What the hell are these fields?
        record0.write(pack('>IIIIIIIIIIIIIIIII',
            0, 0, 0, 0xffffffff, 0, 0xffffffff, 0, 0xffffffff, 0, 0xffffffff,
            0, 0xffffffff, 0, 0xffffffff, 0xffffffff, 1, 0xffffffff))
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
        thumbnail = Image.open(StringIO(item.data))
        thumbnail.thumbnail((180, 240), Image.ANTIALIAS)
        for quality in xrange(95, -1, -1):
            data = StringIO()
            thumbnail.save(data, 'JPEG', quality=quality)
            data = data.getvalue()
            if len(data) <= (1024 * 16):
                break
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
    inpath, outpath = argv[1:]
    oeb = OEBBook(inpath)
    writer = MobiWriter()
    writer.dump(oeb, outpath)
    return 0

if __name__ == '__main__':
    sys.exit(main())
