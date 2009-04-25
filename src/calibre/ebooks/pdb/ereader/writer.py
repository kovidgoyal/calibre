# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Write content to ereader pdb file.
'''

import struct, zlib

from calibre.ebooks.oeb.base import OEB_IMAGES
from calibre.ebooks.pdb.header import PdbHeaderBuilder
from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.pdb.ereader.pmlconverter import html_to_pml

IDENTITY = 'PNPdPPrs'

class Writer(object):
    
    def __init__(self, log):
        self.log = log
        
    def dump(self, oeb_book, out_stream, metadata=None):
        text = self._text(oeb_book.spine)
        images = self._images(oeb_book.manifest)
        metadata = [self._metadata(metadata)]
        
        hr = [self._header_record(len(text), len(images))]
        
        sections = hr+text+images+metadata
        
        lengths = [len(i) for i in sections]
        
        pdbHeaderBuilder = PdbHeaderBuilder(IDENTITY, '')
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
                image += item.data
                
                images.append(image)
                
        return images
        
    def _metadata(self, metadata):
        return ''

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
        else:
            meta_data_offset = text_items + 1
            image_data_offset = meta_data_offset
    
        record = u''
        
        # Version
        record += struct.pack('>H', version)
        record = record.ljust(12, '\x00')
        record += struct.pack('>H', non_text_offset)
        record = record.ljust(40, '\x00')
        record += struct.pack('>H', image_data_offset)
        record = record.ljust(44, '\x00')
        record += struct.pack('>H', meta_data_offset)
        record = record.ljust(52, '\x00')
        record += struct.pack('>H', meta_data_offset)
        
        return record

