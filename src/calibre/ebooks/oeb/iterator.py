from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008 Kovid Goyal <kovid at kovidgoyal.net>'

'''
Iterate over the HTML files in an ebook. Useful for writing viewers.
'''

import re, os, math
from cStringIO import StringIO

from PyQt4.Qt import QFontDatabase

from calibre.customize.ui import available_input_formats
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.zipfile import safe_replace, ZipFile
from calibre.utils.config import DynamicConfig
from calibre.utils.logging import Log
from calibre.ebooks.epub.output import EPUBOutput

TITLEPAGE = EPUBOutput.TITLEPAGE_COVER.decode('utf-8')

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

    def __new__(cls, *args):
        args = list(args)
        path = args[0]
        ppath = path.partition('#')[0]
        if not os.path.exists(path) and os.path.exists(ppath):
            path = ppath
        args[0] = path
        obj = super(SpineItem, cls).__new__(cls, *args)
        raw = open(path, 'rb').read()
        raw, obj.encoding = xml_to_unicode(raw)
        obj.character_count = character_count(raw)
        obj.start_page = -1
        obj.pages      = -1
        obj.max_page   = -1
        return obj

class FakeOpts(object):
    verbose = 0
    breadth_first = False
    max_levels = 5
    input_encoding = None

def is_supported(path):
    ext = os.path.splitext(path)[1].replace('.', '').lower()
    ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
    return ext in available_input_formats()


def write_oebbook(oeb, path):
    from calibre.ebooks.oeb.writer import OEBWriter
    from calibre import walk
    w = OEBWriter()
    w(oeb, path)
    for f in walk(path):
        if f.endswith('.opf'):
            return f

class EbookIterator(object):

    CHARACTERS_PER_PAGE = 1000

    def __init__(self, pathtoebook, log=None):
        self.log = log
        if log is None:
            self.log = Log()
        pathtoebook = pathtoebook.strip()
        self.pathtoebook = os.path.abspath(pathtoebook)
        self.config = DynamicConfig(name='iterator')
        ext = os.path.splitext(pathtoebook)[1].replace('.', '').lower()
        ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
        self.ebook_ext = ext

    def search(self, text, index):
        text = text.lower()
        for i, path in enumerate(self.spine):
            if i > index:
                if text in open(path, 'rb').read().decode(path.encoding).lower():
                    return i

    def find_embedded_fonts(self):
        '''
        This will become unnecessary once Qt WebKit supports the @font-face rule.
        '''
        for item in self.opf.manifest:
            if item.mime_type and 'css' in item.mime_type.lower():
                css = open(item.path, 'rb').read().decode('utf-8', 'replace')
                for match in re.compile(r'@font-face\s*{([^}]+)}').finditer(css):
                    block  = match.group(1)
                    family = re.compile(r'font-family\s*:\s*([^;]+)').search(block)
                    url    = re.compile(r'url\s*\([\'"]*(.+?)[\'"]*\)', re.DOTALL).search(block)
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
                                else:
                                    print 'Loaded embedded font:', repr(family)

    def __enter__(self, raw_only=False):
        self.delete_on_exit = []
        self._tdir = TemporaryDirectory('_ebook_iter')
        self.base  = self._tdir.__enter__()
        from calibre.ebooks.conversion.plumber import Plumber, create_oebbook
        plumber = Plumber(self.pathtoebook, self.base, self.log)
        plumber.setup_options()
        if self.pathtoebook.lower().endswith('.opf'):
            plumber.opts.dont_package = True
        if hasattr(plumber.opts, 'no_process'):
            plumber.opts.no_process = True

        plumber.input_plugin.for_viewer = True
        self.pathtoopf = plumber.input_plugin(open(plumber.input, 'rb'),
                plumber.opts, plumber.input_fmt, self.log,
                {}, self.base)

        if not raw_only and plumber.input_fmt.lower() in ('pdf', 'rb'):
            self.pathtoopf = create_oebbook(self.log, self.pathtoopf, plumber.opts,
                    plumber.input_plugin)
        if hasattr(self.pathtoopf, 'manifest'):
            self.pathtoopf = write_oebbook(self.pathtoopf, self.base)


        self.opf = OPF(self.pathtoopf, os.path.dirname(self.pathtoopf))
        self.language = self.opf.language
        if self.language:
            self.language = self.language.lower()
        self.spine = [SpineItem(i.path) for i in self.opf.spine if i.is_linear]
        self.spine += [SpineItem(i.path) for i in self.opf.spine if not i.is_linear]

        cover = self.opf.cover
        if self.ebook_ext in ('lit', 'mobi', 'prc', 'opf') and cover:
            cfile = os.path.join(os.path.dirname(self.spine[0]),
                    'calibre_iterator_cover.html')
            chtml = (TITLEPAGE%cover).encode('utf-8')
            open(cfile, 'wb').write(chtml)
            self.spine[0:0] = [SpineItem(cfile)]
            self.delete_on_exit.append(cfile)

        if self.opf.path_to_html_toc is not None and \
           self.opf.path_to_html_toc not in self.spine:
            try:
                self.spine.append(SpineItem(self.opf.path_to_html_toc))
            except:
                import traceback
                traceback.print_exc()


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
        self.read_bookmarks()

        return self

    def parse_bookmarks(self, raw):
        for line in raw.splitlines():
            if line.count('^') > 0:
                tokens = line.rpartition('^')
                title, ref = tokens[0], tokens[2]
                self.bookmarks.append((title, ref))

    def serialize_bookmarks(self, bookmarks):
        dat = []
        for title, bm in bookmarks:
            dat.append(u'%s^%s'%(title, bm))
        return (u'\n'.join(dat) +'\n').encode('utf-8')

    def read_bookmarks(self):
        self.bookmarks = []
        bmfile = os.path.join(self.base, 'META-INF', 'calibre_bookmarks.txt')
        raw = ''
        if os.path.exists(bmfile):
            raw = open(bmfile, 'rb').read().decode('utf-8')
        else:
            saved = self.config['bookmarks_'+self.pathtoebook]
            if saved:
                raw = saved
        self.parse_bookmarks(raw)

    def save_bookmarks(self, bookmarks=None):
        if bookmarks is None:
            bookmarks = self.bookmarks
        dat = self.serialize_bookmarks(bookmarks)
        if os.path.splitext(self.pathtoebook)[1].lower() == '.epub' and \
            os.access(self.pathtoebook, os.R_OK):
            try:
                zf = open(self.pathtoebook, 'r+b')
            except IOError:
                return
            zipf = ZipFile(zf, mode='a')
            for name in zipf.namelist():
                if name == 'META-INF/calibre_bookmarks.txt':
                    safe_replace(zf, 'META-INF/calibre_bookmarks.txt', StringIO(dat))
                    return
            zipf.writestr('META-INF/calibre_bookmarks.txt', dat)
        else:
            self.config['bookmarks_'+self.pathtoebook] = dat

    def add_bookmark(self, bm):
        dups = []
        for x in self.bookmarks:
            if x[0] == bm[0]:
                dups.append(x)
        for x in dups:
            self.bookmarks.remove(x)
        self.bookmarks.append(bm)
        self.save_bookmarks()

    def set_bookmarks(self, bookmarks):
        self.bookmarks = bookmarks

    def __exit__(self, *args):
        self._tdir.__exit__(*args)
        for x in self.delete_on_exit:
            if os.path.exists(x):
                os.remove(x)
