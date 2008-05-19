__license__   = 'GPL v3'
__copyright__ = '2008, Anatoly Shipitsin <norguhtar at gmail.com>'
"""
Convert .fb2 files to .lrf
"""
import os, sys, tempfile, subprocess, shutil, logging, glob

from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks import ConversionError
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre import setup_cli_handlers, __appname__
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.resources import fb2_xsl

def option_parser():
    parser = lrf_option_parser(
_('''%prog [options] mybook.fb2


%prog converts mybook.fb2 to mybook.lrf'''))
    parser.add_option('--debug-html-generation', action='store_true', default=False,
                      dest='debug_html_generation', help=_('Print generated HTML to stdout and quit.'))
    return parser
    

def generate_html(fb2file, encoding, logger):
    from lxml import etree
    tdir = tempfile.mkdtemp(prefix=__appname__+'_')
    ofile = os.path.join(tdir, 'index.xml')
    cwd = os.getcwdu()
    os.chdir(tdir)
    try:
        logger.info('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        try:
            doc = etree.parse(fb2file, parser)
        except:
            raise
            logger.info('Parsing failed. Trying to clean up XML...')
            soup = BeautifulStoneSoup(open(fb2file, 'rb').read())
            doc = etree.fromstring(str(soup))
        logger.info('Converting XML to HTML...')
        styledoc = etree.fromstring(fb2_xsl)

        transform = etree.XSLT(styledoc)
        result = transform(doc)
        html = os.path.join(tdir, 'index.html')
        f = open(html, 'wb')
        f.write(transform.tostring(result))
        f.close()
    finally:
        os.chdir(cwd)
    return html
        
def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('fb22lrf')
        setup_cli_handlers(logger, level)
    fb2 = os.path.abspath(os.path.expanduser(path))
    f = open(fb2, 'rb')
    mi = get_metadata(f, 'fb2')
    f.close()
    htmlfile = generate_html(fb2, options.encoding, logger)
    tdir = os.path.dirname(htmlfile)
    cwd = os.getcwdu()
    try:
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        if not mi.title:
            mi.title = os.path.splitext(os.path.basename(rtf))[0]
        if (not options.title or options.title == 'Unknown'):
            options.title = mi.title
        if (not options.author or options.author == 'Unknown') and mi.authors:
            options.author = mi.authors.pop()
        if (not options.category or options.category == 'Unknown') and mi.category:
            options.category = mi.category
        if (not options.freetext or options.freetext == 'Unknown') and mi.comments:
            options.freetext = mi.comments
        os.chdir(tdir)
        html_process_file(htmlfile, options, logger)
    finally:
        os.chdir(cwd)
        if hasattr(options, 'keep_intermediate_files') and options.keep_intermediate_files:
            logger.debug('Intermediate files in '+ tdir)
        else:
            shutil.rmtree(tdir)

def main(args=sys.argv, logger=None):
    parser = option_parser()    
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No fb2 file specified'
        return 1
    process_file(args[1], options, logger)
    return 0

if __name__ == '__main__':
    sys.exit(main())
