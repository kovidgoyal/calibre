__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, shutil, logging
from tempfile import mkdtemp
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks import ConversionError
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre.ebooks.metadata.opf import OPF
from calibre.ebooks.metadata.epub import OCFDirReader
from calibre.libunzip import extract as zip_extract
from calibre import __appname__, setup_cli_handlers


def option_parser():
    return lrf_option_parser(
_('''Usage: %prog [options] mybook.epub
        
        
%prog converts mybook.epub to mybook.lrf''')
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
        htmlfile = ocf.opf.spine[0].path
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
