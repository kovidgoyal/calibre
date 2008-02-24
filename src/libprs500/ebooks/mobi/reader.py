#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Read data from .mobi files
'''

import sys, struct, os, cStringIO, re, atexit, shutil, tempfile

try:
    from PIL import Image as PILImage
except ImportError:
    import Image as PILImage

from libprs500 import __appname__
from libprs500.ebooks.mobi import MobiError
from libprs500.ebooks.mobi.huffcdic import HuffReader
from libprs500.ebooks.mobi.palmdoc import decompress_doc
from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.metadata.opf import OPFCreator


class EXTHHeader(object):
    
    def __init__(self, raw, codec):
        self.doctype = raw[:4]
        self.length, self.num_items = struct.unpack('>LL', raw[4:12])
        raw = raw[12:]
        pos = 0
        
        self.mi = MetaInformation('Unknown', ['Unknown'])
        self.has_fake_cover = True
        
        for i in range(self.num_items):
            id, size = struct.unpack('>LL', raw[pos:pos+8])
            content = raw[pos+8:pos+size]
            pos += size
            if id >= 100 and id < 200:
                self.process_metadata(id, content, codec)
            elif id == 203:
                self.has_fake_cover = bool(struct.unpack('>L', content)[0]) 
            elif id == 201:
                self.cover_offset, = struct.unpack('>L', content)
            elif id == 202:
                self.thumbnail_offset, = struct.unpack('>L', content)
        pos += 3
        stop = raw[pos:].find('\x00')
        if stop > -1:
            self.mi.title = raw[pos:pos+stop].decode(codec, 'ignore')
            
                
    def process_metadata(self, id, content, codec):
        if id == 100:
            aus = content.split(',')
            authors = []
            for a in aus:
                authors.extend(a.split('&'))
            self.mi.authors = [i.decode(codec, 'ignore') for i in authors]
        elif id == 101:
            self.mi.publisher = content.decode(codec, 'ignore')
        elif id == 103:
            self.mi.comments = content.decode(codec, 'ignore')
        elif id == 104:
            self.mi.isbn = content.decode(codec, 'ignore').strip().replace('-', '')
        elif id == 105:
            self.mi.category = content.decode(codec, 'ignore')
         
            

class BookHeader(object):
    
    def __init__(self, raw, ident):
        self.compression_type = raw[:2]
        self.records, self.records_size = struct.unpack('>HH', raw[8:12])
        self.encryption_type, = struct.unpack('>H', raw[12:14])
        self.doctype = raw[16:20]
        self.length, self.type, self.codepage, self.unique_id, self.version = \
                 struct.unpack('>LLLLL', raw[20:40])
        
        if ident == 'TEXTREAD':
            self.codepage = 1252
        
        try:
            self.codec = {
                      1252  : 'cp1252',
                      65001 : 'utf-8',
                      }[self.codepage]
        except IndexError, KeyError:
            raise MobiError('Unknown codepage: %d'%self.codepage)
        
        if ident == 'TEXTREAD' or self.length < 0xF4:
            self.extra_flags = 0
        else:
            self.extra_flags, = struct.unpack('>L', raw[0xF0:0xF4])
        
        
        if self.compression_type == 'DH':
            self.huff_offset, self.huff_number = struct.unpack('>LL', raw[0x70:0x78]) 
        
        self.exth_flag, = struct.unpack('>L', raw[0x80:0x84])
        
        self.exth = None
        if self.exth_flag & 0x40:
            self.exth = EXTHHeader(raw[16+self.length:], self.codec)
            self.exth.mi.uid = self.unique_id
            

class MobiReader(object):
    
    PAGE_BREAK_PAT = re.compile(r'(<[/]{0,1}mbp:pagebreak\s*[/]{0,1}>)+', re.IGNORECASE)
    
    def __init__(self, filename_or_stream):
        if hasattr(filename_or_stream, 'read'):
            stream = filename_or_stream
            stream.seek(0)
        else:
            stream = open(filename_or_stream, 'rb')
            
        raw = stream.read()
        
        self.header   = raw[0:72]
        self.name     = self.header[:32].replace('\x00', '')
        self.num_sections, = struct.unpack('>H', raw[76:78])
        
        self.ident = self.header[0x3C:0x3C+8].upper()
        if self.ident not in ['BOOKMOBI', 'TEXTREAD']:
            raise MobiError('Unknown book type: %s'%self.ident) 
        
        self.sections = []
        self.section_headers = []
        for i in range(self.num_sections):
            offset, a1, a2, a3, a4 = struct.unpack('>LBBBB', raw[78+i*8:78+i*8+8])
            flags, val = a1, a2<<16 | a3<<8 | a4
            self.section_headers.append((offset, flags, val))
        
        def section(section_number):
            if section_number == self.num_sections - 1:
                end_off = len(raw)
            else:
                end_off = self.section_headers[section_number + 1][0]
            off = self.section_headers[section_number][0]
            
            return raw[off:end_off]
            
        for i in range(self.num_sections):
            self.sections.append((section(i), self.section_headers[i])) 
         
            
        self.book_header = BookHeader(self.sections[0][0], self.ident)
        
        
    def extract_content(self, output_dir=os.getcwdu()):
        output_dir = os.path.abspath(output_dir)
        if self.book_header.encryption_type != 0:
            raise MobiError('Cannot extract content from a DRM protected ebook')
        
        processed_records = self.extract_text()
        self.add_anchors()
        self.extract_images(processed_records, output_dir)
        self.replace_page_breaks()
        
        self.processed_html = re.compile('<head>', re.IGNORECASE).sub(
            '<head>\n<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />\n',
                                     self.processed_html)
                
        htmlfile = os.path.join(output_dir, self.name+'.html') 
        open(htmlfile, 'wb').write(self.processed_html.encode('utf8'))
        self.htmlfile = htmlfile
        
        if self.book_header.exth is not None:
            opf = self.create_opf(htmlfile)
            opf.write(open(os.path.splitext(htmlfile)[0]+'.opf', 'wb'))
        
    def create_opf(self, htmlfile):
        mi = self.book_header.exth.mi
        opf = OPFCreator(mi)
        if hasattr(self.book_header.exth, 'cover_offset'):
            opf.cover = 'images/%05d.jpg'%(self.book_header.exth.cover_offset+1)
        manifest = [(os.path.basename(htmlfile), 'text/x-oeb1-document')]
        for i in self.image_names:
            manifest.append(('images/'+i, 'image/jpg'))
        
        opf.create_manifest(manifest)
        opf.create_spine([os.path.basename(htmlfile)])
        return opf
        
        
    def extract_text(self):
        text_sections = [self.sections[i][0] for i in range(1, self.book_header.records+1)]
        processed_records = list(range(0, self.book_header.records+1))
        
        self.mobi_html = u''
        codec = self.book_header.codec
        
        if self.book_header.compression_type == 'DH':
            huffs = [self.sections[i][0] for i in 
                  range(self.book_header.huff_offset, 
                        self.book_header.huff_offset+self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset, 
                        self.book_header.huff_offset+self.book_header.huff_number))
            huff = HuffReader(huffs, self.book_header.extra_flags, codec)
            self.mobi_html = huff.decompress(text_sections)
        
        elif self.book_header.compression_type == '\x00\x02':
            for section in text_sections:
                self.mobi_html += decompress_doc(section, codec)
        
        elif self.book_header.compression_type == '\x00\x01':
            t = [i.decode(codec) for i in text_sections]
            self.mobi_html = ''.join(t)
        
        else:
            raise MobiError('Unknown compression algorithm: %s'%repr(self.book_header.compression_type))
        
        return processed_records
            
    
    def replace_page_breaks(self):
        self.processed_html = self.PAGE_BREAK_PAT.sub('<br style="page-break-after:always" />',
                                                      self.processed_html)
    
    def add_anchors(self):
        positions = []
        link_pattern = re.compile(r'<a\s+filepos=(\d+)', re.IGNORECASE)
        for match in link_pattern.finditer(self.mobi_html):
            positions.append(int(match.group(1)))
        pos = 0
        self.processed_html = ''
        for end in positions:
            oend = end
            l = self.mobi_html.find('<', end)
            r = self.mobi_html.find('>', end)
            if r > -1 and r < l: # Move out of tag
                end = r+1
            self.processed_html += self.mobi_html[pos:end] + '<a name="%d" />'%oend
            pos = end
            
        self.processed_html += self.mobi_html[pos:]
        self.processed_html = link_pattern.sub(lambda match: '<a href="#%d"'%int(match.group(1)), 
                                               self.processed_html)
                
    
    def extract_images(self, processed_records, output_dir):
        output_dir = os.path.abspath(os.path.join(output_dir, 'images'))
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        image_index = 0
        self.image_names = []
        for i in range(self.num_sections):
            if i in processed_records:
                continue
            processed_records.append(i)
            data  = self.sections[i][0]
            buf = cStringIO.StringIO(data)
            try:
                im = PILImage.open(buf)                
            except IOError:
                continue
            image_index += 1 
            path = os.path.join(output_dir, '%05d.jpg'%image_index)
            self.image_names.append(os.path.basename(path))
            im.convert('RGB').save(open(path, 'wb'), format='JPEG')
            
        def fix_images(match):
            one = re.compile(r'src=["\']{0,1}[^\'"]+["\']{0,1}', re.IGNORECASE).sub('', match.group(1)).strip()
            return '<img'+one+' src="images/%s.jpg"'%match.group(2)
        
        if hasattr(self, 'processed_html'):
            self.processed_html = \
            re.compile(r'<img(.+?)recindex=[\'"]{0,1}(\d+)[\'"]{0,1}', re.IGNORECASE|re.DOTALL)\
                .sub(fix_images, self.processed_html)

def get_metadata(stream):
    mr = MobiReader(stream)
    if mr.book_header.exth is None:
        mi = MetaInformation(mr.name, ['Unknown'])
    else:
        tdir = tempfile.mkdtemp('mobi-meta', __appname__)
        atexit.register(shutil.rmtree, tdir)
        mr.extract_images([], tdir)
        mi = mr.create_opf('dummy.html')
        if mi.cover:
            cover =  os.path.join(tdir, mi.cover)
            print cover
            if os.access(cover, os.R_OK):
                mi.cover_data = ('JPEG', open(os.path.join(tdir, mi.cover), 'rb').read())
    return mi
        
def option_parser():
    from libprs500 import OptionParser
    parser = OptionParser(usage='%prog [options] myebook.mobi')
    parser.add_option('-o', '--output-dir', default='.', 
                      help='Output directory. Defaults to current directory.')
    parser.add_option('--verbose', default=False, action='store_true',
                      help='Useful for debugging.')
    return parser
    

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    
    mr = MobiReader(args[1])
    opts.output_dir = os.path.abspath(opts.output_dir)
    mr.extract_content(opts.output_dir)
    if opts.verbose:
        oname = os.path.join(opts.output_dir, 'debug-raw.html')
        open(oname, 'wb').write(mr.mobi_html.encode('utf-8'))
        print 'Raw MOBI HTML saved in', oname
    
    print 'OEB ebook created in', opts.output_dir
    
    return 0

if __name__ == '__main__':
    sys.exit(main())