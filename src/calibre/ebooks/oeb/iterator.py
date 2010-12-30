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
from calibre.utils.zipfile import safe_replace
from calibre.utils.config import DynamicConfig
from calibre.utils.logging import Log
from calibre import guess_type, prints
from calibre.ebooks.oeb.transforms.cover import CoverManager

TITLEPAGE = CoverManager.SVG_TEMPLATE.decode('utf-8').replace(\
        '__ar__', 'none').replace('__viewbox__', '0 0 600 800'
        ).replace('__width__', '600').replace('__height__', '800')

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

    def __new__(cls, path, mime_type=None):
        ppath = path.partition('#')[0]
        if not os.path.exists(path) and os.path.exists(ppath):
            path = ppath
        obj = super(SpineItem, cls).__new__(cls, path)
        raw = open(path, 'rb').read()
        raw, obj.encoding = xml_to_unicode(raw)
        obj.character_count = character_count(raw)
        obj.start_page = -1
        obj.pages      = -1
        obj.max_page   = -1
        if mime_type is None:
            mime_type = guess_type(obj)[0]
        obj.mime_type = mime_type
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

    def search(self, text, index, backwards=False):
        text = text.lower()
        pmap = [(i, path) for i, path in enumerate(self.spine)]
        if backwards:
            pmap.reverse()
        for i, path in pmap:
            if (backwards and i < index) or (not backwards and i > index):
                if text in open(path, 'rb').read().decode(path.encoding).lower():
                    return i

    def find_missing_css_files(self):
        for x in os.walk(os.path.dirname(self.pathtoopf)):
            for f in x[-1]:
                if f.endswith('.css'):
                    yield os.path.join(x[0], f)

    def find_declared_css_files(self):
        for item in self.opf.manifest:
            if item.mime_type and 'css' in item.mime_type.lower():
                yield item.path

    def find_embedded_fonts(self):
        '''
        This will become unnecessary once Qt WebKit supports the @font-face rule.
        '''
        css_files = set(self.find_declared_css_files())
        if not css_files:
            css_files = set(self.find_missing_css_files())
        bad_map = {}
        font_family_pat = re.compile(r'font-family\s*:\s*([^;]+)')
        for csspath in css_files:
            try:
                css = open(csspath, 'rb').read().decode('utf-8', 'replace')
            except:
                continue
            for match in re.compile(r'@font-face\s*{([^}]+)}').finditer(css):
                block  = match.group(1)
                family = font_family_pat.search(block)
                url    = re.compile(r'url\s*\([\'"]*(.+?)[\'"]*\)', re.DOTALL).search(block)
                if url:
                    path = url.group(1).split('/')
                    path = os.path.join(os.path.dirname(csspath), *path)
                    if not os.access(path, os.R_OK):
                        continue
                    id = QFontDatabase.addApplicationFont(path)
                    if id != -1:
                        families = [unicode(f) for f in QFontDatabase.applicationFontFamilies(id)]
                        if family:
                            family = family.group(1)
                            specified_families = [x.strip().replace('"',
                                '').replace("'", '') for x in family.split(',')]
                            aliasing_ok = False
                            for f in specified_families:
                                bad_map[f] = families[0]
                                if not aliasing_ok and f in families:
                                    aliasing_ok = True

                            if not aliasing_ok:
                                prints('WARNING: Family aliasing not fully supported.')
                                prints('\tDeclared family: %r not in actual families: %r'
                                        % (family, families))
                            else:
                                prints('Loaded embedded font:', repr(family))
        if bad_map:
            def prepend_embedded_font(match):
                for bad, good in bad_map.items():
                    if bad in match.group(1):
                        prints('Substituting font family: %s -> %s'%(bad, good))
                        return match.group().replace(bad, '"%s"'%good)

            from calibre.ebooks.chardet import force_encoding
            for csspath in css_files:
                with open(csspath, 'r+b') as f:
                    css = f.read()
                    enc = force_encoding(css, False)
                    css = css.decode(enc, 'replace')
                    ncss = font_family_pat.sub(prepend_embedded_font, css)
                    if ncss != css:
                        f.seek(0)
                        f.truncate()
                        f.write(ncss.encode(enc))

    def __enter__(self, processed=False, only_input_plugin=False):
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
        with plumber.input_plugin:
            self.pathtoopf = plumber.input_plugin(open(plumber.input, 'rb'),
                plumber.opts, plumber.input_fmt, self.log,
                {}, self.base)

        if not only_input_plugin:
            if processed or plumber.input_fmt.lower() in ('pdb', 'pdf', 'rb') and \
                    not hasattr(self.pathtoopf, 'manifest'):
                if hasattr(self.pathtoopf, 'manifest'):
                    self.pathtoopf = write_oebbook(self.pathtoopf, self.base)
                self.pathtoopf = create_oebbook(self.log, self.pathtoopf, plumber.opts,
                        plumber.input_plugin)

        if hasattr(self.pathtoopf, 'manifest'):
            self.pathtoopf = write_oebbook(self.pathtoopf, self.base)

        self.opf = getattr(plumber.input_plugin, 'optimize_opf_parsing', None)
        if self.opf is None:
            self.opf = OPF(self.pathtoopf, os.path.dirname(self.pathtoopf))
        self.language = self.opf.language
        if self.language:
            self.language = self.language.lower()
        ordered = [i for i in self.opf.spine if i.is_linear] + \
                  [i for i in self.opf.spine if not i.is_linear]
        self.spine = []
        for i in ordered:
            spath = i.path
            mt = None
            if i.idref is not None:
                mt = self.opf.manifest.type_for_id(i.idref)
            if mt is None:
                mt = guess_type(spath)[0]
            try:
                self.spine.append(SpineItem(spath, mime_type=mt))
            except:
                self.log.warn('Missing spine item:', repr(spath))

        cover = self.opf.cover
        if self.ebook_ext in ('lit', 'mobi', 'prc', 'opf') and cover:
            cfile = os.path.join(self.base, 'calibre_iterator_cover.html')
            chtml = (TITLEPAGE%os.path.relpath(cover, self.base).replace(os.sep,
                '/')).encode('utf-8')
            open(cfile, 'wb').write(chtml)
            self.spine[0:0] = [SpineItem(cfile,
                mime_type='application/xhtml+xml')]
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
            safe_replace(zf, 'META-INF/calibre_bookmarks.txt', StringIO(dat),
                    add_missing=True)
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
