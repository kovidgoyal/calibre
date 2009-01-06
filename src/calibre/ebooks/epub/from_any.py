from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Convert any ebook format to epub.
'''

import sys, os, re
from contextlib import nested

from calibre import extract, walk
from calibre.ebooks import DRMError
from calibre.ebooks.epub import config as common_config, process_encryption
from calibre.ebooks.epub.from_html import convert as html2epub, find_html_index
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.utils.zipfile import ZipFile
from calibre.customize.ui import run_plugins_on_preprocess

def lit2opf(path, tdir, opts):
    from calibre.ebooks.lit.reader import LitReader
    print 'Exploding LIT file:', path
    reader = LitReader(path)
    reader.extract_content(tdir, False)
    for f in walk(tdir):
        if f.lower().endswith('.opf'):
            return f

def mobi2opf(path, tdir, opts):
    from calibre.ebooks.mobi.reader import MobiReader
    print 'Exploding MOBI file:', path.encode('utf-8') if isinstance(path, unicode) else path
    reader = MobiReader(path)
    reader.extract_content(tdir)
    files = list(walk(tdir))
    opts.encoding = 'utf-8'
    for f in files:
        if f.lower().endswith('.opf'):
            return f
    html_pat = re.compile(r'\.(x){0,1}htm(l){0,1}', re.IGNORECASE)
    hf = [f for f in files if html_pat.match(os.path.splitext(f)[1]) is not None]
    mi = MetaInformation(os.path.splitext(os.path.basename(path))[0], [_('Unknown')])
    opf = OPFCreator(tdir, mi)
    opf.create_manifest([(hf[0], None)])
    opf.create_spine([hf[0]])
    ans = os.path.join(tdir, 'metadata.opf')
    opf.render(open(ans, 'wb'))
    return ans

def fb22opf(path, tdir, opts):
    from calibre.ebooks.lrf.fb2.convert_from import to_html
    print 'Converting FB2 to HTML...'
    return to_html(path, tdir)
    
def rtf2opf(path, tdir, opts):
    from calibre.ebooks.lrf.rtf.convert_from import generate_html
    generate_html(path, tdir)
    return os.path.join(tdir, 'metadata.opf')

def txt2opf(path, tdir, opts):
    from calibre.ebooks.lrf.txt.convert_from import generate_html
    generate_html(path, opts.encoding, tdir)
    return os.path.join(tdir, 'metadata.opf')

def pdf2opf(path, tdir, opts):
    from calibre.ebooks.lrf.pdf.convert_from import generate_html
    generate_html(path, tdir)
    return os.path.join(tdir, 'metadata.opf')

def epub2opf(path, tdir, opts):
    zf = ZipFile(path)
    zf.extractall(tdir)
    opts.chapter_mark = 'none'
    encfile = os.path.join(tdir, 'META-INF', 'encryption.xml')
    opf = None
    for f in walk(tdir):
        if f.lower().endswith('.opf'):
            opf = f
            break
    if opf and os.path.exists(encfile):
        if not process_encryption(encfile, opf):
            raise DRMError(os.path.basename(path))
        
    if opf is None:
        raise ValueError('%s is not a valid EPUB file'%path)
    return opf
    
def odt2epub(path, tdir, opts):
    from calibre.ebooks.odt.to_oeb import Extract
    opts.encoding = 'utf-8'
    return Extract()(path, tdir)

MAP = {
       'lit'  : lit2opf,
       'mobi' : mobi2opf,
       'prc'  : mobi2opf,
       'fb2'  : fb22opf,
       'rtf'  : rtf2opf,
       'txt'  : txt2opf,
       'pdf'  : pdf2opf,
       'epub' : epub2opf,
       'odt'  : odt2epub,
       }
SOURCE_FORMATS = ['lit', 'mobi', 'prc', 'fb2', 'odt', 'rtf', 'txt', 'pdf', 'rar', 'zip', 'oebzip', 'htm', 'html', 'epub']

def unarchive(path, tdir):
    extract(path, tdir)
    files = list(walk(tdir))
    
    for ext in ['opf'] + list(MAP.keys()):
        for f in files:
            if f.lower().endswith('.'+ext):
                if ext in ['txt', 'rtf'] and os.stat(f).st_size < 2048:
                    continue
                return f, ext
    return find_html_index(files)

def any2epub(opts, path, notification=None, create_epub=True, 
             oeb_cover=False, extract_to=None):
    path = run_plugins_on_preprocess(path)
    ext = os.path.splitext(path)[1]
    if not ext:
        raise ValueError('Unknown file type: '+path)
    ext = ext.lower()[1:]
    
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(path))[0]+'.epub'
    
    with nested(TemporaryDirectory('_any2epub1'), TemporaryDirectory('_any2epub2')) as (tdir1, tdir2):
        if ext in ['rar', 'zip', 'oebzip']:
            path, ext = unarchive(path, tdir1)
            print 'Found %s file in archive'%(ext.upper())
    
        if ext in MAP.keys():
            path = MAP[ext](path, tdir2, opts)
            ext = 'opf'
            
    
        if re.match(r'((x){0,1}htm(l){0,1})|opf', ext) is None:
            raise ValueError('Conversion from %s is not supported'%ext.upper())
        
        print 'Creating EPUB file...'
        html2epub(path, opts, notification=notification, 
                  create_epub=create_epub, oeb_cover=oeb_cover,
                  extract_to=extract_to)

def config(defaults=None):
    return common_config(defaults=defaults)


def formats():
    return ['html', 'rar', 'zip', 'oebzip']+list(MAP.keys())

USAGE = _('''\
%%prog [options] filename

Convert any of a large number of ebook formats to a %s file. Supported formats are: %s
''')

def option_parser(usage=USAGE):
    return config().option_parser(usage=usage%('EPUB', formats()))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print 'No input file specified.'
        return 1
    any2epub(opts, args[1])
    return 0

if __name__ == '__main__':
    sys.exit(main())
