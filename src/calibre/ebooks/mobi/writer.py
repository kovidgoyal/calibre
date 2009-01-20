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
import logging
from lxml import etree
from PIL import Image
from calibre.ebooks.oeb.base import XML_NS, XHTML, XHTML_NS, OEB_DOCS, \
    OEB_RASTER_IMAGES
from calibre.ebooks.oeb.base import xpath, barename, namespace, prefixname
from calibre.ebooks.oeb.base import Logger, OEBBook
from calibre.ebooks.oeb.profile import Context
from calibre.ebooks.oeb.transforms.flatcss import CSSFlattener
from calibre.ebooks.oeb.transforms.rasterize import SVGRasterizer
from calibre.ebooks.oeb.transforms.trimmanifest import ManifestTrimmer
from calibre.ebooks.oeb.transforms.htmltoc import HTMLTOCAdder
from calibre.ebooks.oeb.transforms.manglecase import CaseMangler
from calibre.ebooks.mobi.palmdoc import compress_doc
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.ebooks.mobi.mobiml import MBP_NS, MBP, MobiMLizer
from calibre.customize.ui import run_plugins_on_postprocess
from calibre.utils.config import Config, StringConfig

# TODO:
# - Allow override CSS (?)
# - Generate index records
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
            path, frag = urldefrag(ref.href)
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
        path, frag = urldefrag(href)
        if path and base:
            path = base.abshref(path)
        if path and path not in hrefs:
            return False
        buffer = self.buffer
        item = hrefs[path] if path else None
        if item and item.spine_position is None:
            return False
        path =  item.href if item else base.href
        href = '#'.join((path, frag)) if frag else path
        buffer.write('filepos=')
        self.href_offsets[href].append(buffer.tell())
        buffer.write('0000000000')
        return True
        
    def serialize_body(self):
        buffer = self.buffer
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
        for attr in ('name', 'id'):
            if attr in elem.attrib:
                href = '#'.join((item.href, elem.attrib[attr]))
                self.id_offsets[href] = buffer.tell()
                del elem.attrib[attr]
        if tag == 'a' and not elem.attrib \
           and not len(elem) and not elem.text:
            return
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
    
    def __init__(self, compression=None, imagemax=None):
        self._compression = compression or UNCOMPRESSED
        self._imagemax = imagemax or OTHER_MAX_IMAGE_SIZE

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
        self._text_length = len(text)
        text = StringIO(text)
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
            nrecords += 1
            offset += RECORD_SIZE
            data, overlap = self._read_text_record(text)
        self._text_nrecords = nrecords

    def _rescale_image(self, data, maxsizeb, dimen=None):
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
        
    def _generate_images(self):
        self._oeb.logger.info('Serializing images...')
        images = [(index, href) for href, index in self._images.items()]
        images.sort()
        metadata = self._oeb.metadata
        coverid = metadata.cover[0] if metadata.cover else None
        for _, href in images:
            item = self._oeb.manifest.hrefs[href]
            data = self._rescale_image(item.data, self._imagemax)
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
                data = self.COLLAPSE_RE.sub(' ', unicode(item))
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
            index = self._add_thumbnail(item) - 1
            exth.write(pack('>III', 0xca, 0x0c, index))
            nrecs += 3
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '' if not trail else '\0' * (4 - trail)
        exth = ['EXTH', pack('>II', len(exth) + 12, nrecs), exth, pad]
        return ''.join(exth)

    def _add_thumbnail(self, item):
        data = self._rescale_image(item.data, MAX_THUMB_SIZE, MAX_THUMB_DIMEN)
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


def config(defaults=None):
    desc = _('Options to control the conversion to MOBI')
    _profiles = list(sorted(Context.PROFILES.keys()))
    if defaults is None:
        c = Config('mobi', desc)
    else:
        c = StringConfig(defaults, desc)
        
    mobi = c.add_group('mobipocket', _('Mobipocket-specific options.'))
    mobi('compress', ['--compress'], default=False,
         help=_('Compress file text using PalmDOC compression. '
               'Results in smaller files, but takes a long time to run.'))
    mobi('rescale_images', ['--rescale-images'], default=False, 
        help=_('Modify images to meet Palm device size limitations.'))
    mobi('toc_title', ['--toc-title'], default=None, 
         help=_('Title for any generated in-line table of contents.'))
    profiles = c.add_group('profiles', _('Device renderer profiles. '
        'Affects conversion of font sizes, image rescaling and rasterization '
        'of tables. Valid profiles are: %s.') % ', '.join(_profiles))
    profiles('source_profile', ['--source-profile'],
             default='Browser', choices=_profiles,
             help=_("Source renderer profile. Default is %default."))
    profiles('dest_profile', ['--dest-profile'],
             default='CybookG3', choices=_profiles,
             help=_("Destination renderer profile. Default is %default."))
    c.add_opt('encoding', ['--encoding'], default=None,
              help=_('Character encoding for HTML files. Default is to auto detect.'))
    return c
    

def option_parser():
    c = config()
    parser = c.option_parser(usage='%prog '+_('[options]')+' file.opf')
    parser.add_option(
        '-o', '--output', default=None, 
        help=_('Output file. Default is derived from input filename.'))
    parser.add_option(
        '-v', '--verbose', default=0, action='count',
        help=_('Useful for debugging.'))
    return parser

def oeb2mobi(opts, inpath):
    logger = Logger(logging.getLogger('oeb2mobi'))
    logger.setup_cli_handler(opts.verbose)
    outpath = opts.output
    if outpath is None:
        outpath = os.path.basename(inpath)
        outpath = os.path.splitext(outpath)[0] + '.mobi'
    source = opts.source_profile
    if source not in Context.PROFILES:
        logger.error(_('Unknown source profile %r') % source)
        return 1
    dest = opts.dest_profile
    if dest not in Context.PROFILES:
        logger.error(_('Unknown destination profile %r') % dest)
        return 1
    compression = PALMDOC if opts.compress else UNCOMPRESSED
    imagemax = PALM_MAX_IMAGE_SIZE if opts.rescale_images else None
    context = Context(source, dest)
    oeb = OEBBook(inpath, logger=logger)
    tocadder = HTMLTOCAdder(title=opts.toc_title)
    tocadder.transform(oeb, context)
    mangler = CaseMangler()
    mangler.transform(oeb, context)
    fbase = context.dest.fbase
    fkey = context.dest.fnums.values()
    flattener = CSSFlattener(
        fbase=fbase, fkey=fkey, unfloat=True, untable=True)
    flattener.transform(oeb, context)
    rasterizer = SVGRasterizer()
    rasterizer.transform(oeb, context)
    trimmer = ManifestTrimmer()
    trimmer.transform(oeb, context)
    mobimlizer = MobiMLizer()
    mobimlizer.transform(oeb, context)
    writer = MobiWriter(compression=compression, imagemax=imagemax)
    writer.dump(oeb, outpath)
    run_plugins_on_postprocess(outpath, 'mobi')
    logger.info(_('Output written to ') + outpath)
    
def main(argv=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(argv[1:])
    if len(args) != 1:
        parser.print_help()
        return 1
    inpath = args[0]
    retval = oeb2mobi(opts, inpath)
    return retval

if __name__ == '__main__':
    sys.exit(main())
