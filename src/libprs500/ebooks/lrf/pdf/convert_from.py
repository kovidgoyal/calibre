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
from libprs500 import filename_to_utf8
''''''

import sys, os, subprocess, logging
from libprs500 import isosx, setup_cli_handlers
from libprs500.ebooks import ConversionError
from libprs500.ptempfile import PersistentTemporaryFile
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file

PDFTOHTML = 'pdftohtml'
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(sys.frameworks_dir, PDFTOHTML)


def generate_html(pathtopdf, logger):
    '''
    Convert the pdf into html.
    @return: A closed PersistentTemporaryFile.
    '''
    if not os.access(pathtopdf, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtopdf
    pf = PersistentTemporaryFile('.html')
    pf.close()
    # This is neccessary as pdftohtml doesn't always (linux) respect absolute paths
    cmd = PDFTOHTML + ' -noframes -p -nomerge "%s" "%s"'%(pathtopdf, os.path.basename(pf.name))
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(pf.name)) 
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, 
                             stdout=subprocess.PIPE)
        logger.info(p.stdout.read())
        ret = p.wait()
        if ret != 0:
            err = p.stderr.read()
            raise ConversionError, err
    finally:
        os.chdir(cwd)
    return pf

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.pdf\n\n'''
        '''%prog converts mybook.pdf to mybook.lrf\n\n'''
        )

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('pdf2lrf')
        setup_cli_handlers(logger, level)
    pdf = os.path.abspath(os.path.expanduser(path))
    htmlfile = generate_html(pdf, logger)
    if not options.output:
        ext = '.lrs' if options.lrs else '.lrf'        
        options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
    else:
        options.output = os.path.abspath(options.output)
    options.pdftohtml = True
    if not options.title:
        options.title = filename_to_utf8(os.path.splitext(os.path.basename(options.output))[0])
    html_process_file(htmlfile.name, options, logger)


def main(args=sys.argv, logger=None):
    from libprs500 import set_translator
    set_translator()
    
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:            
        parser.print_help()
        print
        print 'No pdf file specified'
        return 1
    process_file(args[1], options, logger)
    return 0

if __name__ == '__main__':
    sys.exit(main())