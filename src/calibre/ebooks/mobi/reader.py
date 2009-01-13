from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Read data from .mobi files
'''

import sys, struct, os, cStringIO, re, atexit, shutil, tempfile

try:
    from PIL import Image as PILImage
except ImportError:
    import Image as PILImage

from lxml import html, etree

from calibre import __appname__, entity_to_unicode
from calibre.ebooks import DRMError
from calibre.ebooks.chardet import ENCODING_PATS
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.mobi.palmdoc import decompress_doc
from calibre.ebooks.mobi.langcodes import main_language, sub_language
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.metadata.toc import TOC
from calibre import sanitize_file_name

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
            #else:
            #    print 'unknown record', id, repr(content)
        title = re.search(r'\0+([^\0]+)\0+', raw[pos:])
        if title:
            title = title.group(1).decode(codec, 'replace')
            if len(title) > 2:
                self.mi.title = title
            else:
                title = re.search(r'\0+([^\0]+)\0+', ''.join(reversed(raw[pos:])))
                if title:
                    self.mi.title = ''.join(reversed(title.group(1).decode(codec, 'replace')))
            
                
    def process_metadata(self, id, content, codec):
        if id == 100:
            self.mi.authors   = [content.decode(codec, 'ignore').strip()]
        elif id == 101:
            self.mi.publisher = content.decode(codec, 'ignore').strip()
        elif id == 103:
            self.mi.comments  = content.decode(codec, 'ignore')
        elif id == 104:
            self.mi.isbn      = content.decode(codec, 'ignore').strip().replace('-', '')
        elif id == 105:
            if not self.mi.tags:
                self.mi.tags = []
            self.mi.tags.append(content.decode(codec, 'ignore'))
        #else:
        #    print 'unhandled metadata record', id, repr(content), codec 
            

class BookHeader(object):
    
    def __init__(self, raw, ident):
        self.compression_type = raw[:2]
        self.records, self.records_size = struct.unpack('>HH', raw[8:12])
        self.encryption_type, = struct.unpack('>H', raw[12:14])
        if ident == 'TEXTREAD':
            self.codepage = 1252
        if len(raw) <= 16:
            self.codec = 'cp1251'
            self.extra_flags = 0
            self.language = 'ENGLISH'
            self.sublanguage = 'NEUTRAL'
            self.exth_flag, self.exth = 0, None
            self.ancient = True
        else:
            self.ancient = False
            self.doctype = raw[16:20]
            self.length, self.type, self.codepage, self.unique_id, self.version = \
                     struct.unpack('>LLLLL', raw[20:40])
                    
            
            try:
                self.codec = {
                          1252  : 'cp1252',
                          65001 : 'utf-8',
                          }[self.codepage]
            except (IndexError, KeyError):
                print '[WARNING] Unknown codepage %d. Assuming cp-1252'%self.codepage
                self.codec = 'cp1252'
            
            if ident == 'TEXTREAD' or self.length < 0xE4 or 0xE8 < self.length:
                self.extra_flags = 0
            else:
                self.extra_flags, = struct.unpack('>H', raw[0xF2:0xF4])
            
            if self.compression_type == 'DH':
                self.huff_offset, self.huff_number = struct.unpack('>LL', raw[0x70:0x78]) 
            
            langcode  = struct.unpack('!L', raw[0x5C:0x60])[0]
            langid    = langcode & 0xFF
            sublangid = (langcode >> 10) & 0xFF
            self.language = main_language.get(langid, 'ENGLISH')
            self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')
            
            self.exth_flag, = struct.unpack('>L', raw[0x80:0x84])
            self.exth = None
            if self.exth_flag & 0x40:
                self.exth = EXTHHeader(raw[16+self.length:], self.codec)
                self.exth.mi.uid = self.unique_id
                self.exth.mi.language = self.language
            

class MobiReader(object):
    
    PAGE_BREAK_PAT = re.compile(r'(<[/]{0,1}mbp:pagebreak\s*[/]{0,1}>)+', re.IGNORECASE)
    IMAGE_PATS     = map(re.compile, (r'\shirecindex=[\'"]{0,1}(\d+)[\'"]{0,1}', 
                        r'\srecindex=[\'"]{0,1}(\d+)[\'"]{0,1}', 
                        r'\slorecindex=[\'"]{0,1}(\d+)[\'"]{0,1}'))
    
    def __init__(self, filename_or_stream, verbose=False):
        self.verbose = verbose
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
        self.name = self.name.decode(self.book_header.codec, 'replace')
        
    def extract_content(self, output_dir=os.getcwdu()):
        output_dir = os.path.abspath(output_dir)
        if self.book_header.encryption_type != 0:
            raise DRMError(self.name)
        
        processed_records = self.extract_text()
        self.add_anchors()
        self.processed_html = self.processed_html.decode(self.book_header.codec, 'ignore')
        for pat in ENCODING_PATS:
            self.processed_html = pat.sub('', self.processed_html)
        self.extract_images(processed_records, output_dir)
        self.replace_page_breaks()
        self.cleanup_html()
        
        if self.processed_html.startswith('<body'):
            self.processed_html = '<html><head></head>'+self.processed_html+'</html>'
        self.processed_html = \
            re.compile('<head>', re.IGNORECASE).sub(
                '\n<head>\n'
                '<style type="text/css">\n'
                'blockquote { margin: 0em 0em 0em 1.25em; text-align: justify; }\n'
                'p { margin: 0em; text-align: justify; }\n'
                '.bold { font-weight: bold; }\n'
                '.italic { font-style: italic; }\n'
                '</style>\n',
                self.processed_html)
        
        if self.verbose:
            print 'Parsing HTML...'
        root = html.fromstring(self.processed_html)
        self.upshift_markup(root)
        guides = root.xpath('//guide')
        guide = guides[0] if guides else None
        for elem in guides + root.xpath('//metadata'):
            elem.getparent().remove(elem)
        htmlfile = os.path.join(output_dir, 
                                sanitize_file_name(self.name)+'.html')
        try:
            for ref in guide.xpath('descendant::reference'):
                if ref.attrib.has_key('href'):
                    ref.attrib['href'] = os.path.basename(htmlfile)+ref.attrib['href']
        except AttributeError:
            pass
        if self.verbose:
            print 'Serializing...'
        with open(htmlfile, 'wb') as f:
            raw = html.tostring(root, encoding='utf-8', method='xml', 
                         include_meta_content_type=True, pretty_print=True)
            raw = raw.replace('<head>', 
            '<head>\n<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />\n')
            f.write(raw)
        self.htmlfile = htmlfile
        
        if self.book_header.exth is not None:
            if self.verbose:
                print 'Creating OPF...'
            ncx = cStringIO.StringIO()
            opf = self.create_opf(htmlfile, guide)
            opf.render(open(os.path.splitext(htmlfile)[0]+'.opf', 'wb'), ncx)
            ncx = ncx.getvalue()
            if ncx:
                open(os.path.splitext(htmlfile)[0]+'.ncx', 'wb').write(ncx)
        
    def cleanup_html(self):
        if self.verbose:
            print 'Cleaning up HTML...'
        self.processed_html = re.sub(r'<div height="0(pt|px|ex|em|%){0,1}"></div>', '', self.processed_html)
        if self.book_header.ancient and '<html' not in self.mobi_html[:300].lower():
            self.processed_html = '<html><p>'+self.processed_html.replace('\n\n', '<p>')+'</html>'
        self.processed_html = self.processed_html.replace('> <', '>\n<')
        for t, c in [('b', 'bold'), ('i', 'italic')]:
            self.processed_html = re.sub(r'(?i)<%s>'%t, r'<span class="%s">'%c, self.processed_html)
            self.processed_html = re.sub(r'(?i)</%s>'%t, r'</span>', self.processed_html)
        
    def upshift_markup(self, root):
        if self.verbose:
            print 'Converting style information to CSS...'
        size_map = {
                    'xx-small' : '0.5',
                    'x-small'  : '1',
                    'small'    : '2',
                    'medium'   : '3',
                    'large'    : '4',
                    'x-large'  : '5',
                    'xx-large' : '6',
                    }
        for tag in root.iter(etree.Element):
            styles, attrib = [], tag.attrib
            if attrib.has_key('style'):
                style = attrib.pop('style').strip()
                if style:
                    styles.append(style)
            if attrib.has_key('height'):
                height = attrib.pop('height').strip()
                if height:
                    styles.append('margin-top: %s' % height)
            if attrib.has_key('width'):
                width = attrib.pop('width').strip()
                if width:
                    styles.append('text-indent: %s' % width)
                    if width.startswith('-'):
                        styles.append('margin-left: %s'%(width[1:]))
            if attrib.has_key('align'):
                align = attrib.pop('align').strip()
                if align:
                    styles.append('text-align: %s' % align)
            if styles:
                attrib['style'] = '; '.join(styles)
                
            if tag.tag.lower() == 'font':
                sz = tag.get('size', '').lower()
                try:
                    float(sz)
                except ValueError:
                    if sz in size_map.keys():
                        attrib['size'] = size_map[sz]
    
    def create_opf(self, htmlfile, guide=None):
        mi = self.book_header.exth.mi
        opf = OPFCreator(os.path.dirname(htmlfile), mi)
        if hasattr(self.book_header.exth, 'cover_offset'):
            opf.cover = 'images/%05d.jpg'%(self.book_header.exth.cover_offset+1)
        manifest = [(htmlfile, 'text/x-oeb1-document')]
        bp = os.path.dirname(htmlfile)
        for i in self.image_names:
            manifest.append((os.path.join(bp, 'images/', i), 'image/jpg'))
        
        opf.create_manifest(manifest)
        opf.create_spine([os.path.basename(htmlfile)])
        toc = None
        if guide is not None:
            opf.create_guide(guide)
            for ref in opf.guide:
                if ref.type.lower() == 'toc':
                    toc = ref.href()
        if toc:
            index = self.processed_html.find('<a id="%s" name="%s"'%(toc.partition('#')[-1], toc.partition('#')[-1]))
            tocobj = None
            ent_pat = re.compile(r'&(\S+?);')
            if index > -1:
                raw = '<html><body>'+self.processed_html[index:]
                root = html.fromstring(raw)
                tocobj = TOC()
                for a in root.xpath('//a[@href]'):
                    try:
                        text = u' '.join([t.strip() for t in a.xpath('descendant::text()')])
                    except:
                        text = ''
                    text = ent_pat.sub(entity_to_unicode, text)
                    if a.get('href', '').startswith('#'):
                        tocobj.add_item(toc.partition('#')[0], a.attrib['href'][1:], text)
            if tocobj is not None:
                opf.set_toc(tocobj)
        
        return opf
        
        
    def sizeof_trailing_entries(self, data):
        def sizeof_trailing_entry(ptr, psize):
            bitpos, result = 0, 0
            while True:
                v = ord(ptr[psize-1])
                result |= (v & 0x7F) << bitpos
                bitpos += 7
                psize -= 1
                if (v & 0x80) != 0 or (bitpos >= 28) or (psize == 0):
                    return result
        
        num = 0
        size = len(data)
        flags = self.book_header.extra_flags >> 1
        while flags:
            if flags & 1:
                num += sizeof_trailing_entry(data, size - num)
            flags >>= 1
        if self.book_header.extra_flags & 1:
            num += (ord(data[size - num - 1]) & 0x3) + 1
        return num

    def text_section(self, index):
        data = self.sections[index][0]
        trail_size = self.sizeof_trailing_entries(data)
        return data[:len(data)-trail_size]
    
    def extract_text(self):
        if self.verbose:
            print 'Extracting text...'
        text_sections = [self.text_section(i) for i in range(1, self.book_header.records+1)]
        processed_records = list(range(0, self.book_header.records+1))
        
        self.mobi_html = ''
        
        if self.book_header.compression_type == 'DH':
            huffs = [self.sections[i][0] for i in 
                  range(self.book_header.huff_offset, 
                        self.book_header.huff_offset+self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset, 
                        self.book_header.huff_offset+self.book_header.huff_number))
            huff = HuffReader(huffs)
            self.mobi_html = huff.decompress(text_sections)
        
        elif self.book_header.compression_type == '\x00\x02':
            for section in text_sections:
                self.mobi_html += decompress_doc(section)
        
        elif self.book_header.compression_type == '\x00\x01':
            self.mobi_html = ''.join(text_sections)
        else:
            raise MobiError('Unknown compression algorithm: %s'%repr(self.book_header.compression_type))
        if self.book_header.ancient and '<html' not in self.mobi_html[:300].lower():
            self.mobi_html = self.mobi_html.replace('\r ', '\n\n ')
        return processed_records
            
    
    def replace_page_breaks(self):
        self.processed_html = self.PAGE_BREAK_PAT.sub('<br style="page-break-after:always" />',
                                                      self.processed_html)
    
    def add_anchors(self):
        if self.verbose:
            print 'Adding anchors...'
        positions = set([])
        link_pattern = re.compile(r'<[^<>]+filepos=[\'"]{0,1}(\d+)[^<>]*>', re.IGNORECASE)
        for match in link_pattern.finditer(self.mobi_html):
            positions.add(int(match.group(1)))
        positions = list(positions)
        positions.sort()
        pos = 0
        self.processed_html = ''
        for end in positions:
            if end == 0:
                continue
            oend = end
            l = self.mobi_html.find('<', end)
            r = self.mobi_html.find('>', end)
            if r > -1 and r < l: # Move out of tag
                end = r+1
            self.processed_html += self.mobi_html[pos:end] + '<a id="filepos%d" name="filepos%d"></a>'%(oend, oend) 
            pos = end
            
        self.processed_html += self.mobi_html[pos:]
        fpat = re.compile(r'filepos=[\'"]{0,1}(\d+)[\'"]{0,1}', re.IGNORECASE)
        def fpos_to_href(match):
            return fpat.sub('href="#filepos%d"'%int(match.group(1)), match.group())
        self.processed_html = link_pattern.sub(fpos_to_href, 
                                               self.processed_html)
        
    def extract_images(self, processed_records, output_dir):
        if self.verbose:
            print 'Extracting images...'
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
            tag = match.group()
            for pat in self.IMAGE_PATS:
                m = pat.search(tag)
                if m:
                    return pat.sub(' src="images/%s.jpg"'%m.group(1), tag)
                    
        
        if hasattr(self, 'processed_html'):
            self.processed_html = \
            re.compile(r'<img (.*?)>', re.IGNORECASE|re.DOTALL)\
                .sub(fix_images, self.processed_html)

def get_metadata(stream):
    mr = MobiReader(stream)
    if mr.book_header.exth is None:
        mi = MetaInformation(mr.name, ['Unknown'])
    else:
        tdir = tempfile.mkdtemp('_mobi_meta', __appname__)
        atexit.register(shutil.rmtree, tdir)
        mr.extract_images([], tdir)
        mi = mr.create_opf('dummy.html')
        if mi.cover:
            cover =  os.path.join(tdir, mi.cover)
            if os.access(cover, os.R_OK):
                mi.cover_data = ('JPEG', open(os.path.join(tdir, mi.cover), 'rb').read())
        else:
            path = os.path.join(tdir, 'images', '00001.jpg')
            if os.access(path, os.R_OK):
                mi.cover_data = ('JPEG', open(path, 'rb').read())
    return mi
        
def option_parser():
    from calibre.utils.config import OptionParser
    parser = OptionParser(usage=_('%prog [options] myebook.mobi'))
    parser.add_option('-o', '--output-dir', default='.', 
                      help=_('Output directory. Defaults to current directory.'))
    parser.add_option('--verbose', default=False, action='store_true',
                      help='Useful for debugging.')
    return parser
    

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    
    mr = MobiReader(args[1], verbose=opts.verbose)
    opts.output_dir = os.path.abspath(opts.output_dir)
    mr.extract_content(opts.output_dir)
    if opts.verbose:
        oname = os.path.join(opts.output_dir, 'debug-raw.html')
        dat = mr.mobi_html
        if isinstance(dat, unicode):
            dat = dat.encode('utf-8')
        open(oname, 'wb').write(dat)
        print _('Raw MOBI HTML saved in'), oname
    
    print _('OEB ebook created in'), opts.output_dir
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
