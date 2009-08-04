# -*- coding: utf-8 -*-

'''
Write content to ereader pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import struct
import zlib

try:
    from PIL import Image
    Image
except ImportError:
    import Image

import cStringIO

from calibre.ebooks.pdb.formatwriter import FormatWriter
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.pml.pmlml import PMLMLizer

IDENTITY = 'PNRdPPrs'

# This is an arbitrary number that is small enough to work. The actual maximum
# record size is unknown.
MAX_RECORD_SIZE = 3560

class Writer(FormatWriter):

    def __init__(self, opts, log):
        self.opts = opts
        self.log = log

    def write_content(self, oeb_book, out_stream, metadata=None):
        text = self._text(oeb_book)
        images = self._images(oeb_book.manifest)
        metadata = [self._metadata(metadata)]

        hr = [self._header_record(len(text), len(images))]

        sections = hr+text+images+metadata+['MeTaInFo\x00']

        lengths = [len(i) if i not in images else len(i[0]) + len(i[1]) for i in sections]

        pdbHeaderBuilder = PdbHeaderBuilder(IDENTITY, metadata[0].partition('\x00')[0])
        pdbHeaderBuilder.build_header(lengths, out_stream)

        for item in sections:
            if item in images:
                out_stream.write(item[0])
                out_stream.write(item[1])
            else:
                out_stream.write(item)

    def _text(self, oeb_book):
        pmlmlizer = PMLMLizer(self.log)
        pml = unicode(pmlmlizer.extract_content(oeb_book, self.opts)).encode('cp1252', 'replace')

        pml_pages = []
        for i in range(0, (len(pml) / MAX_RECORD_SIZE) + 1):
            pml_pages.append(zlib.compress(pml[i * MAX_RECORD_SIZE : (i * MAX_RECORD_SIZE) + MAX_RECORD_SIZE]))

        return pml_pages

    def _images(self, manifest):
        images = []

        for item in manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    im = Image.open(cStringIO.StringIO(item.data)).convert('P')
                    im.thumbnail((300,300), Image.ANTIALIAS)

                    data = cStringIO.StringIO()
                    im.save(data, 'PNG')
                    data = data.getvalue()

                    header = 'PNG '
                    header += image_name(item.href)
                    header = header.ljust(62, '\x00')

                    if len(data) + len(header) < 65505:
                        images.append((header, data))
                except Exception as e:
                    self.log.error('Error: Could not include file %s becuase ' \
                        '%s.' % (item.href, e))

        return images

    def _metadata(self, metadata):
        '''
        Metadata takes the form:
        title\x00
        author\x00
        copyright\x00
        publisher\x00
        isbn\x00
        '''

        title = _('Unknown')
        author = _('Unknown')
        copyright = ''
        publisher = ''
        isbn = ''

        if metadata:
            if len(metadata.title) >= 1:
                title = metadata.title[0].value
            if len(metadata.creator) >= 1:
                from calibre.ebooks.metadata import authors_to_string
                author = authors_to_string([x.value for x in metadata.creator])
            if len(metadata.rights) >= 1:
                copyright = metadata.rights[0].value
            if len(metadata.publisher) >= 1:
                publisher = metadata.publisher[0].value

        return '%s\x00%s\x00%s\x00%s\x00%s\x00' % (title, author, copyright, publisher, isbn)

    def _header_record(self, text_items, image_items):
        '''
        text_items = the number of text pages
        image_items = the number of images
        '''
        version = 10 # Zlib compression
        non_text_offset = text_items + 1

        if image_items > 0:
            image_data_offset = text_items + 1
            meta_data_offset = image_data_offset + image_items
            last_data_offset = meta_data_offset + 1
        else:
            meta_data_offset = text_items + 1
            last_data_offset = meta_data_offset + 1
            image_data_offset = last_data_offset

        record = ''

        record += struct.pack('>H', version)                # [0:2]    # Version. Specifies compression and drm. 2 = palmdoc, 10 = zlib. 260 and 272 = DRM
        record += struct.pack('>H', 0)                      # [2:4]
        record += struct.pack('>H', 0)                      # [4:6]
        record += struct.pack('>H', 25152)                  # [6:8]    # 25152 is MAGIC. Somehow represents the cp1252 encoding of the text
        record += struct.pack('>H', 0)                      # [8:10]
        record += struct.pack('>H', 0)                      # [10:12]
        record += struct.pack('>H', non_text_offset)        # [12:14]  # non_text_offset
        record += struct.pack('>H', 0)                      # [14:16]
        record += struct.pack('>H', 0)                      # [16:18]
        record += struct.pack('>H', 0)                      # [18:20]
        record += struct.pack('>H', image_items)            # [20:22]  # Number of images
        record += struct.pack('>H', 0)                      # [22:24]
        record += struct.pack('>H', 1)                      # [24:26]  # 1 if has metadata, 0 if not
        record += struct.pack('>H', 0)                      # [26:28]
        record += struct.pack('>H', 0)                      # [28:30]  # footnote_rec
        record += struct.pack('>H', 0)                      # [30:32]  # sidebar_rec
        record += struct.pack('>H', last_data_offset)       # [32:34]  # bookmark_offset
        record += struct.pack('>H', 2560)                   # [34:36]  # 2560 is MAGIC
        record += struct.pack('>H', 0)                      # [36:38]
        record += struct.pack('>H', 0)                      # [38:40]
        record += struct.pack('>H', image_data_offset)      # [40:42]  # image_data_offset. This will be the last data offset if there are no images
        record += struct.pack('>H', 0)                      # [42:44]
        record += struct.pack('>H', meta_data_offset)       # [44:46]  # meta_data_offset. This will be the last data offset if there are no images
        record += struct.pack('>H', 0)                      # [46:48]
        record += struct.pack('>H', last_data_offset)       # [48:50]  # footnote_offset. This will be the last data offset if there are no images
        record += struct.pack('>H', last_data_offset)       # [50:52]  # sidebar_offset. This will be the last data offset if there are no images
        record += struct.pack('>H', last_data_offset)       # [52:54]  # last_data_offset

        for i in range(54, 132, 2):
            record += struct.pack('>H', 0)                  # [54:132]

        return record

