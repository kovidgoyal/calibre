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
''''''

import sys, tempfile, os, logging, shutil

from libprs500 import setup_cli_handlers, __appname__
from libprs500.ebooks.mobi.reader import MobiReader
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file

def generate_html(mobifile, tdir):
    mr = MobiReader(mobifile)
    mr.extract_content(tdir)
    return mr.htmlfile

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('lit2lrf')
        setup_cli_handlers(logger, level)
    mobi = os.path.abspath(os.path.expanduser(path))
    tdir = tempfile.mkdtemp('mobi2lrf', __appname__)
    try:
        htmlfile = generate_html(mobi, tdir)
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

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.mobi|prc\n\n'''
        '''%prog converts mybook.mobi to mybook.lrf'''
        )


def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:            
        parser.print_help()
        print
        print 'No mobi file specified'
        return 1
    process_file(args[1], options, logger)

    return 0

if __name__ == '__main__':
    sys.exit(main())