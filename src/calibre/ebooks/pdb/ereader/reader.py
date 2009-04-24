# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Read content from ereader pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, sys, struct, zlib

from calibre import CurrentDir
from calibre.ebooks import DRMError
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.ereader import EreaderError
from calibre.ebooks.pdb.ereader.pmlconverter import pml_to_html, \
    footnote_to_html, sidebar_to_html 
from calibre.ebooks.mobi.palmdoc import decompress_doc
from calibre.ebooks.metadata.opf2 import OPFCreator

class HeaderRecord(object):
    '''
    The first record in the file is always the header record. It holds
    information related to the location of text, images, and so on
    in the file. This is used in conjunction with the sections
    defined in the file header.
    '''

    def __init__(self, raw):
        self.version, = struct.unpack('>H', raw[0:2])
        self.non_text_offset, = struct.unpack('>H', raw[12:14]) 
        self.footnote_rec, = struct.unpack('>H', raw[28:30])
        self.sidebar_rec, =  struct.unpack('>H', raw[30:32])
        self.bookmark_offset, = struct.unpack('>H', raw[32:34])
        self.image_data_offset, = struct.unpack('>H', raw[40:42])
        self.metadata_offset, = struct.unpack('>H', raw[44:46])
        self.footnote_offset, = struct.unpack('>H', raw[48:50])
        self.sidebar_offset, = struct.unpack('>H', raw[50:52])
        self.last_data_offset, = struct.unpack('>H', raw[52:54])
        
        self.num_text_pages = self.non_text_offset -1
        self.num_image_pages = self.metadata_offset - self.image_data_offset

        # Can't tell which is sidebar and footnote if they have same offset.
        # They don't exist if offset is larget than last_record.
        # Todo: Determine if the subtraction is necessary and find out
        # what _rec means.
        end_footnote_offset = self.sidebar_offset if self.sidebar_offset != self.footnote_offset else self.last_data_offset
        self.num_footnote_pages = end_footnote_offset - self.footnote_offset if self.footnote_offset < self.last_data_offset else 0 
        self.num_sidebar_pages = self.sidebar_offset - self.last_data_offset if self.footnote_offset < self.last_data_offset else 0
        

class Reader(FormatReader):

    def __init__(self, header, stream, log, encoding=None):
        self.log = log
        self.encoding = encoding
    
        self.sections = []
        for i in range(header.num_sections):
            self.sections.append(header.section_data(i))

        self.header_record = HeaderRecord(self.section_data(0))

        if self.header_record.version not in (2, 10):
            if self.header_record.version in (260, 272):
                raise DRMError('eReader DRM is not supported.')
            else:
                raise EreaderError('Unknown book version %i.' % self.header_record.version)
        
    def section_data(self, number):
        return self.sections[number]
        
    def decompress_text(self, number):
        if self.header_record.version == 2:
            return decompress_doc(self.section_data(number)).decode('cp1252' if self.encoding is None else self.encoding)
        if self.header_record.version == 10:
            return zlib.decompress(self.section_data(number)).decode('cp1252' if self.encoding is None else self.encoding)

        
    def get_image(self, number):
        if number < self.header_record.image_data_offset or number > self.header_record.image_data_offset + self.header_record.num_image_pages - 1:
            return 'empty', ''
        data = self.section_data(number)
        name = data[4:4+32].strip('\0')
        img = data[62:]
        return name, img
        
    def get_text_page(self, number):
        '''
        Only palmdoc and zlib compressed are supported. The text is
        assumed to be encoded as Windows-1252. The encoding is part of
        the eReader file spec and should always be this encoding.
        '''
        if number not in range(1, self.header_record.num_text_pages):
            return ''
            
        return self.decompress_text(number)
            
    def get_footnote_page(self, number):
        if number not in range(self.header_record.footnote_offset, self.header_record.footnote_offset + self.header_record.num_footnote_pages):
            return ''
            
        return self.decompress_text(number)
        
    def get_sidebar_page(self, number):
        if number not in range(self.header_record.sidebar_offset, self.header_record.sidebar_offset + self.header_record.num_sidebar_pages - 1):
            return ''
            
        return self.decompress_text(number)

    def has_footnotes(self):
        if self.header_record.num_footnote_pages > 1:
            try:
                content = self.decompress_text(self.header_record.footnote_offset)
                
                if content.contains('</footnote>'):
                    return True
            except:
                pass
        return False
        
    def has_sidebar(self):
        if self.header_record.num_sidebar_pages > 1:
            try:
                content = self.decompress_text(self.header_record.sidebar_offset)
                
                if content.contains('</sidebar>'):
                    return True
            except:
                pass
        return False

    def extract_content(self, output_dir):
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        html = '<html><head><title></title></head><body>'
        
        for i in range(1, self.header_record.num_text_pages + 1):
            self.log.debug('Extracting text page %i' % i)
            html += pml_to_html(self.get_text_page(i))

        # Untested: The num_.._pages variable may not be correct!
        # Possibly use .._rec instead?
        '''
        if has_footnotes():
            html += '<br /><h1>%s</h1>' % _('Footnotes')
            for i in range(self.header_record.footnote_offset, self.header_record.num_footnote_pages):
                self.log.debug('Extracting footnote page %i' % i)
                html += footnote_to_html(self.get_footnote_page(i))
                
        if has_sidebar():
            html += '<br /><h1>%s</h1>' % _('Sidebar')
            for i in range(self.header_record.sidebar_offset, self.header_record.num_sidebar_pages):
                self.log.debug('Extracting sidebar page %i' % i)
                html += sidebar_to_html(self.get_sidebar_page(i))
        '''
        
        html += '</body></html>'
        
        with CurrentDir(output_dir):
            with open('index.html', 'wb') as index:
                self.log.debug('Writing text to index.html')
                index.write(html.encode('utf-8'))
        
        if not os.path.exists(os.path.join(output_dir, 'images/')):
            os.makedirs(os.path.join(output_dir, 'images/'))
        images = []
        with CurrentDir(os.path.join(output_dir, 'images/')):
            for i in range(0, self.header_record.num_image_pages):
                name, img = self.get_image(self.header_record.image_data_offset + i)
                images.append(name)
                with open(name, 'wb') as imgf:
                    self.log.debug('Writing image %s to images/' % name)
                    imgf.write(img)
            
        opf_path = self.create_opf(output_dir, images)
            
        return opf_path
        
    def create_opf(self, output_dir, images):
        mi = MetaInformation(None, None)
        
        with CurrentDir(output_dir):
            opf = OPFCreator(output_dir, mi)
            
            manifest = [('index.html', None)]
        
            for i in images:
                manifest.append((os.path.join('images/', i), None))
        
            opf.create_manifest(manifest)
            opf.create_spine(['index.html'])
            with open('metadata.opf', 'wb') as opffile:
                opf.render(opffile)
                
        return os.path.join(output_dir, 'metadata.opf')
        
    def dump_pml(self):
        '''
        This is primarily used for debugging and 3rd party tools to
        get the plm markup that comprises the text in the file.
        '''
        pml = ''
        
        for i in range(1, self.header_record.num_text_pages + 1):
            pml += self.get_text_page(i)
        
        return pml
        
    def dump_images(self, output_dir):
        '''
        This is primarily used for debugging and 3rd party tools to
        get the images in the file.
        '''
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with CurrentDir(output_dir):            
            for i in range(0, self.header_record.num_image_pages):
                name, img = self.get_image(self.header_record.image_data_offset + i)
                with open(name, 'wb') as imgf:
                    imgf.write(img)

