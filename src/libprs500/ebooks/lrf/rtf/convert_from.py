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
import os, sys, tempfile, subprocess, shutil, logging

from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file
from libprs500.ebooks import ConversionError
from libprs500 import isosx, setup_cli_handlers

UNRTF = 'unrtf'
if isosx and hasattr(sys, 'frameworks_dir'):
    UNRTF = os.path.join(sys.frameworks_dir, UNRTF)

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.rtf\n\n'''
        '''%prog converts mybook.rtf to mybook.lrf'''
        )

def generate_html(rtfpath, logger):
    tdir = tempfile.mkdtemp(prefix='rtf2lrf_')
    cwd = os.path.abspath(os.getcwd())
    os.chdir(tdir)
    try:
        logger.info('Converting to HTML...')
        sys.stdout.flush()
        handle, path = tempfile.mkstemp(dir=tdir, suffix='.html')
        file = os.fdopen(handle, 'wb')
        cmd = ' '.join([UNRTF, '"'+rtfpath+'"'])
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        file.write(p.stdout.read())
        ret = p.wait()
        if ret != 0:
            if isosx and ret == -11: #unrtf segfaults on OSX but seems to convert most of the file.
                file.write('</body>\n</html>')
            else:
                logger.critical(p.stderr.read())
                raise ConversionError, 'unrtf failed with error code: %d'%(ret,)
        file.close()
        return path        
    finally:
        os.chdir(cwd)
        
def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('pdf2lrf')
        setup_cli_handlers(logger, level)
    rtf = os.path.abspath(os.path.expanduser(path))
    f = open(rtf, 'rb')
    mi = get_metadata(f, 'rtf')
    f.close()
    html = generate_html(rtf, logger)
    tdir = os.path.dirname(html)
    try:
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        if (not options.title or options.title == 'Unknown') and mi.title:
            sys.argv.append('-t')
            sys.argv.append('"'+mi.title+'"')
        if (not options.author or options.author == 'Unknown') and mi.author:
            sys.argv.append('-a')
            sys.argv.append('"'+mi.author+'"')
        if (not options.category or options.category == 'Unknown') and mi.category:
            sys.argv.append('--category')
            sys.argv.append('"'+mi.category+'"')
        if (not options.freetext or options.freetext == 'Unknown') and mi.comments:
            sys.argv.append('--comment')
            sys.argv.append('"'+mi.comments+'"')
        html_process_file(html, options, logger)
    finally:
        shutil.rmtree(tdir)

def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No rtf file specified'
        return 1
    process_file(args[1], options, logger)
    return 0
    
    
            
if __name__ == '__main__':
    sys.exit(main())
    
        