__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''Convert any ebook file into a LRF file.'''

import sys, os, logging, shutil, tempfile, glob

from calibre.ebooks import UnknownFormatError
from calibre.ebooks.lrf import option_parser as _option_parser
from calibre import __appname__, setup_cli_handlers, extract
from calibre.ebooks.lrf.lit.convert_from  import process_file as lit2lrf
from calibre.ebooks.lrf.pdf.convert_from  import process_file as pdf2lrf
from calibre.ebooks.lrf.rtf.convert_from  import process_file as rtf2lrf
from calibre.ebooks.lrf.txt.convert_from  import process_file as txt2lrf
from calibre.ebooks.lrf.html.convert_from import process_file as html2lrf
from calibre.ebooks.lrf.epub.convert_from import process_file as epub2lrf
from calibre.ebooks.lrf.mobi.convert_from import process_file as mobi2lrf
from calibre.ebooks.lrf.fb2.convert_from  import process_file as fb22lrf

def largest_file(files):
    maxsize, file = 0, None
    for f in files:
        size = os.stat(f).st_size
        if size > maxsize:
            maxsize = size
            file = f
    return file

def find_htmlfile(dir):
    cwd = os.getcwd()
    try:
        os.chdir(dir)
        for pair in (('*toc*.htm*', '*toc*.xhtm*'), ('*.htm*', '*.xhtm*')):
            files = glob.glob(pair[0])
            files += glob.glob(pair[1])
            file = largest_file(files)
            if file:
                return os.path.join(dir, file)
    finally:
        os.chdir(cwd)

def number_of_unhidden_files(base, listing):
    ans = 0
    for i in listing:
        i = os.path.join(base, i)
        if os.path.isdir(i) or os.path.basename(i).startswith('.'):
            continue
        ans += 1
    return ans

def unhidden_directories(base, listing):
    ans = []
    for i in listing:
        if os.path.isdir(os.path.join(base, i)) and not i.startswith('__') and \
           not i.startswith('.'):
            ans.append(i)
    return ans

def traverse_subdirs(tdir):
    temp = os.listdir(tdir)
    if number_of_unhidden_files(tdir, temp) == 0:
        try:
            cdir = os.path.join(tdir, unhidden_directories(tdir, temp)[0])
            return traverse_subdirs(cdir)
        except IndexError:
            pass
    return tdir

def handle_archive(path):
    tdir = tempfile.mkdtemp(prefix=__appname__+'_')
    extract(path, tdir)
    files = []
    cdir = traverse_subdirs(tdir)
    file = None
    for ext in ('lit', 'rtf', 'pdf', 'txt', 'epub', 'mobi', 'prc'):
        pat = os.path.join(cdir, '*.'+ext)
        files.extend(glob.glob(pat))
    file = largest_file(files)
    if file:
        return tdir, file
    file = find_htmlfile(cdir)
    return tdir, file 

def process_file(path, options, logger=None):
    path = os.path.abspath(os.path.expanduser(path))
    tdir = None
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('any2lrf')
        setup_cli_handlers(logger, level)
    if not os.access(path, os.R_OK):
        logger.critical('Cannot read from %s', path)
        return 1
    ext = os.path.splitext(path)[1]
    if not ext or ext == '.':
        logger.critical('Unknown file type: %s', path)
        return 1
    ext = ext[1:].lower()
    cwd = os.getcwd()
    if not options.output:
        fmt = '.lrs' if options.lrs else '.lrf'
        options.output = os.path.splitext(os.path.basename(path))[0] + fmt
    options.output = os.path.abspath(os.path.expanduser(options.output))
    if ext in ['zip', 'rar']:
        newpath = None
        try:
            tdir, newpath = handle_archive(path)
        except:
            logger.exception(' ')
        if not newpath:
            raise UnknownFormatError('Could not find ebook in archive')
        path = newpath
        logger.info('Found ebook in archive: %s', path)
    try:
        ext = os.path.splitext(path)[1][1:].lower()
        convertor = None
        if 'htm' in ext:
            convertor = html2lrf
        elif 'lit' == ext:
            convertor = lit2lrf
        elif 'pdf' == ext:
            convertor = pdf2lrf
        elif 'rtf' == ext:
            convertor = rtf2lrf
        elif 'txt' == ext:
            convertor = txt2lrf
        elif 'epub' == ext:
            convertor = epub2lrf
        elif ext in ['mobi', 'prc']:
            convertor = mobi2lrf
        elif ext == 'fb2':
            convertor = fb22lrf
        if not convertor:
            raise UnknownFormatError('Coverting from %s to LRF is not supported.'%ext)
        convertor(path, options, logger)
    finally:
        os.chdir(cwd)
        if tdir and os.path.exists(tdir):
            shutil.rmtree(tdir)
    return 0
    

def option_parser(gui_mode=False):
    return _option_parser(usage=_('''\
any2lrf [options] myfile

Convert any ebook format into LRF. Supported formats are:
LIT, RTF, TXT, HTML, EPUB, MOBI, PRC and PDF. any2lrf will also process a RAR or
ZIP archive, looking for an ebook inside the archive.
    '''), gui_mode=gui_mode)


def main(args=sys.argv, logger=None, gui_mode=False):
    parser = option_parser(gui_mode) 
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print _('No file to convert specified.')
        return 1
    
    return process_file(args[1], options, logger)

if __name__ == '__main__':
    sys.exit(main())
