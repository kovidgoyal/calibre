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

import os, sys, shutil, glob, logging
from tempfile import mkdtemp
from subprocess import Popen, PIPE
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file
from libprs500.ebooks.metadata.opf import OPFReader, OPF
from libprs500.ebooks.metadata.epub import OCFDirReader
from libprs500.libunzip import extract as zip_extract
from libprs500 import isosx, __appname__, setup_cli_handlers, iswindows


def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.epub\n\n'''
        '''%prog converts mybook.epub to mybook.lrf'''
        )

def generate_html(pathtoepub, logger):
    if not os.access(pathtoepub, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtoepub
    tdir = mkdtemp(prefix=__appname__+'_')
    os.rmdir(tdir)
    try:
        zip_extract(pathtoepub, tdir)
    except:
        if os.path.exists(tdir) and os.path.isdir(tdir):
            shutil.rmtree(tdir)        
        raise ConversionError, '.epub extraction failed'
    return tdir

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('epub2lrf')
        setup_cli_handlers(logger, level)
    epub = os.path.abspath(os.path.expanduser(path))
    tdir = generate_html(epub, logger)
    try:
        ocf = OCFDirReader(tdir)
        htmlfile = ocf.opf.spine.items().next().href
        options.opf = os.path.join(tdir, ocf.container[OPF.MIMETYPE])
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        options.use_spine = True
        
        html_process_file(htmlfile, options, logger=logger)
    finally:
        try:
            shutil.rmtree(tdir)
        except:
            logger.warning('Failed to delete temporary directory '+tdir)


def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:            
        parser.print_help()
        print
        print 'No epub file specified'
        return 1
    process_file(args[1], options, logger)
    return 0        
        
            
if __name__ == '__main__':
    sys.exit(main())
