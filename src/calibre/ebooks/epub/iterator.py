__license__   = 'GPL v3'
__copyright__ = '2008 Kovid Goyal <kovid at kovidgoyal.net>'

'''
Iterate over the HTML files in an ebook. Useful for writing viewers.
'''

import re, os, math, copy

from PyQt4.Qt import QFontDatabase

from calibre.ebooks.epub.from_any import MAP
from calibre.ebooks.epub.from_html import TITLEPAGE
from calibre.ebooks.epub import config 
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.html import create_dir

def character_count(html):
    '''
    Return the number of "significant" text characters in a HTML string.
    '''
    count = 0
    strip_space = re.compile(r'\s+')
    for match in re.finditer(r'>[^<]+<', html):
        count += len(strip_space.sub(' ', match.group()))-2
    return count

class UnsupportedFormatError(Exception):
    
    def __init__(self, fmt):
        Exception.__init__(self, _('%s format books are not supported')%fmt.upper()) 

class SpineItem(unicode):
    
    def __init__(self, path):
        unicode.__init__(self, path)
        raw = open(path, 'rb').read()
        raw, self.encoding = xml_to_unicode(raw)
        self.character_count = character_count(raw)
        self.start_page = -1
        self.pages      = -1
        self.max_page   = -1

def html2opf(path, tdir, opts):
    opts = copy.copy(opts)
    opts.output = tdir
    create_dir(path, opts)
    return os.path.join(tdir, 'metadata.opf')

def opf2opf(path, tdir, opts):
    return path

def is_supported(path):
    ext = os.path.splitext(path)[1].replace('.', '').lower()
    ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
    return ext in list(MAP.keys())+['html', 'opf']

class EbookIterator(object):
    
    CHARACTERS_PER_PAGE = 1000
    
    def __init__(self, pathtoebook):
        self.pathtoebook = pathtoebook
        ext = os.path.splitext(pathtoebook)[1].replace('.', '').lower()
        ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
        map = dict(MAP)
        map['html'] = html2opf
        map['opf']  = opf2opf
        if ext not in map.keys():
            raise UnsupportedFormatError(ext)
        self.to_opf = map[ext]
    
    def search(self, text, index):
        text = text.lower()
        for i, path in enumerate(self.spine):
            if i > index:
                if text in open(path, 'rb').read().decode(path.encoding).lower():
                    return i
    
    def find_embedded_fonts(self):
        for item in self.opf.manifest:
            if item.mime_type and 'css' in item.mime_type.lower():
                css = open(item.path, 'rb').read().decode('utf-8')
                for match in re.compile(r'@font-face\s*{([^}]+)}').finditer(css):
                    block  = match.group(1)
                    family = re.compile(r'font-family\s*:\s*([^;]+)').search(block)
                    url    = re.compile(r'url\s*\((.+?)\)', re.DOTALL).search(block)
                    if url:
                        path = url.group(1).split('/')
                        path = os.path.join(os.path.dirname(item.path), *path) 
                        id = QFontDatabase.addApplicationFont(path)
                        if id != -1:
                            families = [unicode(f) for f in QFontDatabase.applicationFontFamilies(id)]
                            if family:
                                family = family.group(1).strip().replace('"', '')
                                if family not in families:
                                    print 'WARNING: Family aliasing not supported:', block
    
    def __enter__(self):
        self._tdir = TemporaryDirectory('_ebook_iter')
        self.base  = self._tdir.__enter__()
        opts = config('').parse()
        self.pathtoopf = self.to_opf(self.pathtoebook, self.base, opts)
        self.opf = OPF(self.pathtoopf, os.path.dirname(self.pathtoopf))
        self.spine = [SpineItem(i.path) for i in self.opf.spine]
        
        cover = self.opf.cover
        if os.path.splitext(self.pathtoebook)[1].lower() in ('.lit', '.mobi', '.prc') and cover:
            cfile = os.path.join(os.path.dirname(self.spine[0]), 'calibre_ei_cover.html')
            open(cfile, 'wb').write(TITLEPAGE%cover)
            self.spine[0:0] = [SpineItem(cfile)]
        
        sizes = [i.character_count for i in self.spine]
        self.pages = [math.ceil(i/float(self.CHARACTERS_PER_PAGE)) for i in sizes]
        for p, s in zip(self.pages, self.spine):
            s.pages = p
        start = 1
        
        
        for s in self.spine:
            s.start_page = start
            start += s.pages
            s.max_page = s.start_page + s.pages - 1
        self.toc = self.opf.toc
        
        self.find_embedded_fonts() 
        
        return self
        
    def __exit__(self, *args):
        self._tdir.__exit__(*args)