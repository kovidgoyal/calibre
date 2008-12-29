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
from lxml import etree
from calibre.ebooks.mobi.palmdoc import compress_doc
from calibre.ebooks.lit.oeb import XHTML, XHTML_NS, OEB_DOCS
from calibre.ebooks.lit.oeb import barename, namespace
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


class Serializer(object):
    def __init__(self, oeb, images):
        self.oeb = oeb
        self.images = images
        self.root = etree.Element(XHTML('html'),
            nsmap={None: XHTML_NS, 'mbp': MBP_NS})
        self.generate_head()
        self.generate_body()

    def __str__(self):
        return etree.tostring(self.root)

    def generate_head(self):
        head = etree.SubElement(self.root, XHTML('head'))

    def generate_body(self):
        body = etree.SubElement(self.root, XHTML('body'))
        first = True
        for item in self.oeb.spine:
            if item.media_type not in OEB_DOCS: continue
            for elem in item.data.find(XHTML('body')):
                body.append(elem)
            etree.SubElement(body, MBP('pagebreak'))

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
    def __init__(self, compress=PALMDOC, logger=FauxLogger()):
        self._compress = compress or 1
        self._logger = logger

    def dump(self, oeb, path):
        if hasattr(path, 'write'):
            return self._dump_stream(oeb, path)
        with open(path, 'w+b') as stream:
            return self._dump_stream(oeb, stream)
    
    def _write(self, *data):
        for datum in data:
            self._stream.write(datum)
    
    @preserve
    def _writeat(self, pos, *data):
        self._stream.seek(pos)
        self._write(*data)
    
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
        index = 0
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
        pass
    
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
        npad = 4 - (record0.tell() % 4)
        if npad < 4: record0.write('\0' * npad)
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
        exth = exth.getvalue()
        return ''.join(['EXTH', pack('>II', len(exth) + 12, nrecs), exth])

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
