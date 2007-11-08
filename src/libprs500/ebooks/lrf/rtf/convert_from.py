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
import os, sys, tempfile, subprocess, shutil, logging, glob

from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.metadata.meta import get_metadata
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file
from libprs500.ebooks import ConversionError
from libprs500 import isosx, setup_cli_handlers, __appname__
from libprs500.libwand import convert, WandException

UNRTF   = 'unrtf'
if isosx and hasattr(sys, 'frameworks_dir'):
    UNRTF   = os.path.join(getattr(sys, 'frameworks_dir'), UNRTF)

def option_parser():
    return lrf_option_parser(
        '''Usage: %prog [options] mybook.rtf\n\n'''
        '''%prog converts mybook.rtf to mybook.lrf'''
        )

def convert_images(html, logger):
    wmfs = glob.glob('*.wmf') + glob.glob('*.WMF')
    for wmf in wmfs:
        target = os.path.join(os.path.dirname(wmf), os.path.splitext(os.path.basename(wmf))[0]+'.jpg')
        try:
            convert(wmf, target)
            html = html.replace(os.path.basename(wmf), os.path.basename(target))
        except WandException, err:
            logger.warning(u'Unable to convert image %s with error: %s'%(wmf, unicode(err)))
            continue
    return html

def generate_html(rtfpath, logger):
    tdir = tempfile.mkdtemp(prefix=__appname__+'_')
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
        raw = p.stdout.read()
        ret = p.wait()
        if ret != 0:
            if len(raw) > 1000: #unrtf crashes occassionally on OSX and windows but still convert correctly
                raw += '</body>\n</html>'
            else:
                logger.critical(p.stderr.read())
                raise ConversionError, 'unrtf failed with error code: %d'%(ret,)
        file.write(convert_images(raw, logger))
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
        if not mi.title:
            mi.title = os.path.splitext(os.path.basename(rtf))[0]
        if (not options.title or options.title == 'Unknown'):
            options.title = mi.title
        if (not options.author or options.author == 'Unknown') and mi.author:
            options.author = mi.author
        if (not options.category or options.category == 'Unknown') and mi.category:
            options.category = mi.category
        if (not options.freetext or options.freetext == 'Unknown') and mi.comments:
            options.freetext = mi.comments
        html_process_file(html, options, logger)
    finally:
        shutil.rmtree(tdir)

def main(args=sys.argv, logger=None):
    from libprs500 import set_translator
    set_translator()
    
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
    
        