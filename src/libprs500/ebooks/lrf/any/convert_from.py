##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
'''Convert any ebook file into a LRF file.'''

import sys, os, logging, shutil, tempfile, glob

from libprs500.ebooks import UnknownFormatError
from libprs500.ebooks.lrf import option_parser
from libprs500 import __appname__, setup_cli_handlers, extract
from libprs500.ebooks.lrf.lit.convert_from  import process_file as lit2lrf
from libprs500.ebooks.lrf.pdf.convert_from  import process_file as pdf2lrf
from libprs500.ebooks.lrf.rtf.convert_from  import process_file as rtf2lrf
from libprs500.ebooks.lrf.txt.convert_from  import process_file as txt2lrf
from libprs500.ebooks.lrf.html.convert_from import process_file as html2lrf

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
    

def handle_archive(path):
    tdir = tempfile.mkdtemp(prefix=__appname__+'_')
    extract(path, tdir)
    files = []
    cdir = tdir
    temp = os.listdir(tdir)
    file = None
    if len(temp) == 1 and os.path.isdir(os.path.join(tdir, temp[0])):
        cdir = os.path.join(tdir, temp[0])
    for ext in ('lit', 'rtf', 'pdf', 'txt'):
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
            logger.critical('Could not find ebook in archive')
            return 1
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
        if not convertor:
            raise UnknownFormatError('Coverting from %s to LRF is not supported.')
        convertor(path, options, logger)
    finally:
        os.chdir(cwd)
        if tdir and os.path.exists(tdir):
            shutil.rmtree(tdir)
    return 0
    

def main(args=sys.argv, logger=None):
    parser = option_parser('''\
any2lrf myfile

Convert any ebook format into LRF. Supported formats are:
LIT, RTF, TXT, HTML and PDF. any2lrf will also process a RAR or
ZIP archive.
    ''')
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No file to convert specified.'
        return 1
    
    return process_file(args[1], options, logger)

if __name__ == '__main__':
    sys.exit(main())