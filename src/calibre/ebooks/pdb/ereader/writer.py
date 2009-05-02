# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Write content to ereader pdb file.
'''

import struct, zlib

import Image, cStringIO

from calibre.ebooks.oeb.base import OEB_IMAGES
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.pml.pmlconverter import html_to_pml

IDENTITY = 'PNPdPPrs'

class Writer(object):
    
    def __init__(self, log):
        self.log = log
        
    def dump(self, oeb_book, out_stream, metadata=None):
        text = self._text(oeb_book.spine)
        images = self._images(oeb_book.manifest)
        metadata = [self._metadata(metadata)]
        
        hr = [self._header_record(len(text), len(images))]
        
        sections = hr+text+images+metadata+['MeTaInFo\x00']
        
        lengths = [len(i) for i in sections]
        
        pdbHeaderBuilder = PdbHeaderBuilder(IDENTITY, 'test book')
        pdbHeaderBuilder.build_header(lengths, out_stream)
        
        for item in sections:
            out_stream.write(item)

    def _text(self, pages):
        pml_pages = []
        
        for page in pages:
            pml_pages.append(zlib.compress(html_to_pml(unicode(page)).encode('utf-8')))

        return pml_pages            
        
    def _images(self, manifest):
        images = []
        
        for item in manifest:
            if item.media_type in OEB_IMAGES:
                image = '\x00\x00\x00\x00'

                image += image_name(item.href)
                image = image.ljust(62, '\x00')
                
                im = Image.open(cStringIO.StringIO(item.data))
                
                data = cStringIO.StringIO()
                im.save(data, 'PNG')
                data = data.getvalue()
                
                image += data
                
                if len(image) < 65505:
                    images.append(image)
                
        return images
        
    def _metadata(self, metadata):
        return 'test\x00\x00\x00\x00\x00'

    def _header_record(self, text_items, image_items):
        '''
        text_items = the number of text pages
        image_items = the number of images
        '''
        version = 10
        non_text_offset = text_items + 1
        
        if image_items > 0:
            image_data_offset = text_items + 1
            meta_data_offset = image_data_offset + image_items
            last_data_offset = meta_data_offset + 2
        else:
            meta_data_offset = text_items + 1
            last_data_offset = meta_data_offset + 1
            image_data_offset = last_data_offset
    
        record = ''
        
        record += struct.pack('>H', version)                # [0:2]
        record += struct.pack('>H', 0)                      # [2:4]
        record += struct.pack('>H', 0)                      # [4:6]
        record += struct.pack('>H', 25152)                  # [6:8]   # 25152 is MAGIC
        record += struct.pack('>H', last_data_offset)       # [8:10]
        record += struct.pack('>H', last_data_offset)       # [10:12]
        record += struct.pack('>H', non_text_offset)        # [12:14] # non_text_offset
        record += struct.pack('>H', non_text_offset)        # [14:16]
        record += struct.pack('>H', 1)                      # [16:18]
        record += struct.pack('>H', 1)                      # [18:20]
        record += struct.pack('>H', 0)                      # [20:22]
        record += struct.pack('>H', 1)                      # [22:24]
        record += struct.pack('>H', 1)                      # [24:26]
        record += struct.pack('>H', 0)                      # [26:28]
        record += struct.pack('>H', 0)                      # [28:30] # footnote_rec
        record += struct.pack('>H', 0)                      # [30:32] # sidebar_rec
        record += struct.pack('>H', last_data_offset)       # [32:34] # bookmark_offset
        record += struct.pack('>H', 2560)                   # [34:36] # 2560 is MAGIC
        record += struct.pack('>H', non_text_offset)        # [36:38]
        record += struct.pack('>H', non_text_offset + 1)    # [38:40]
        record += struct.pack('>H', image_data_offset)      # [40:42]
        record += struct.pack('>H', image_data_offset)      # [42:44]
        record += struct.pack('>H', meta_data_offset)       # [44:46]
        record += struct.pack('>H', meta_data_offset)       # [46:48]
        record += struct.pack('>H', last_data_offset)       # [48:50] # footnote_offset
        record += struct.pack('>H', last_data_offset)       # [50:52] # sidebar_offset
        record += struct.pack('>H', last_data_offset)       # [52:54] # last_data_offset

        record += struct.pack('>H', 1)       # [54:56]
        for i in range(56, 132, 2):
            record += struct.pack('>H', 0)
        
        '''
        # Version
        record += struct.pack('>H', version)
        record = record.ljust(12, '\x00')
        # Non-text offset, everything between record 0 and non_text_offset is text pages
        record += struct.pack('>H', non_text_offset)
        record = record.ljust(28, '\x00')
        # Footnote and Sidebar rec
        record += struct.pack('>H', 0)
        record += struct.pack('>H', 0)
        record += struct.pack('>H', last_data_offset)
        record = record.ljust(40, '\x00')
        # image pages
        record += struct.pack('>H', image_data_offset)
        record = record.ljust(44, '\x00')
        # metadata string
        record += struct.pack('>H', meta_data_offset)
        record = record.ljust(48, '\x00')
        # footnote and sidebar offsets
        record += struct.pack('>H', last_data_offset)
        record += struct.pack('>H', last_data_offset)
        record = record.ljust(52, '\x00')
        record += struct.pack('>H', last_data_offset)
        '''
        return record

