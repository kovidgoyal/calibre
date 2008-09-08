__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, sys, tempfile, shutil, logging, glob

from lxml import etree

from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre import isosx, setup_cli_handlers, __appname__
from calibre.libwand import convert, WandException
from calibre.ebooks.BeautifulSoup import BeautifulStoneSoup
from calibre.ebooks.lrf.rtf.xsl import xhtml

UNRTF   = 'unrtf'
if isosx and hasattr(sys, 'frameworks_dir'):
    UNRTF   = os.path.join(getattr(sys, 'frameworks_dir'), UNRTF)

def option_parser():
    parser = lrf_option_parser(
_('''%prog [options] mybook.rtf


%prog converts mybook.rtf to mybook.lrf''')
        )
    parser.add_option('--keep-intermediate-files', action='store_true', default=False)
    return parser

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

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('rtf2lrf')
        setup_cli_handlers(logger, level)
    rtf = os.path.abspath(os.path.expanduser(path))
    f = open(rtf, 'rb')
    mi = get_metadata(f, 'rtf')
    f.close()
    html = generate_html(rtf, logger)
    tdir = os.path.dirname(html)
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
        if (not options.author or options.author == 'Unknown') and mi.author:
            options.author = mi.author
        if (not options.category or options.category == 'Unknown') and mi.category:
            options.category = mi.category
        if (not options.freetext or options.freetext == 'Unknown') and mi.comments:
            options.freetext = mi.comments
        os.chdir(tdir)
        html_process_file(html, options, logger)
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
        print 'No rtf file specified'
        return 1
    process_file(args[1], options, logger)
    return 0
    

def generate_xml(rtfpath):
    from calibre.ebooks.rtf2xml.ParseRtf import ParseRtf
    tdir = tempfile.mkdtemp(prefix=__appname__+'_')
    ofile = os.path.join(tdir, 'index.xml')
    cwd = os.getcwdu()
    os.chdir(tdir)
    try:
        parser = ParseRtf(
            in_file    = rtfpath,
            out_file   = ofile,
            # Convert symbol fonts to unicode equivelents. Default
            # is 1
            convert_symbol = 1,
    
            # Convert Zapf fonts to unicode equivelents. Default
            # is 1.
            convert_zapf = 1,
    
            # Convert Wingding fonts to unicode equivelents.
            # Default is 1.
            convert_wingdings = 1,
    
            # Convert RTF caps to real caps.
            # Default is 1.
            convert_caps = 1,
    
            # Indent resulting XML.
            # Default is 0 (no indent).
            indent = 1,
    
            # Form lists from RTF. Default is 1.
            form_lists = 1,
    
            # Convert headings to sections. Default is 0.
            headings_to_sections = 1,
    
            # Group paragraphs with the same style name. Default is 1.
            group_styles = 1,
    
            # Group borders. Default is 1.
            group_borders = 1,
    
            # Write or do not write paragraphs. Default is 0.
            empty_paragraphs = 0,
        )
        parser.parse_rtf()
    finally:
        os.chdir(cwd)
    return ofile


def generate_html(rtfpath, logger):
    logger.info('Converting RTF to XML...')
    xml = generate_xml(rtfpath)
    tdir = os.path.dirname(xml)
    cwd = os.getcwdu()
    os.chdir(tdir)
    try:
        logger.info('Parsing XML...')
        parser = etree.XMLParser(recover=True, no_network=True)
        try:
            doc = etree.parse(xml, parser)
        except:
            raise
            logger.info('Parsing failed. Trying to clean up XML...')
            soup = BeautifulStoneSoup(open(xml, 'rb').read())
            doc = etree.fromstring(str(soup))
        logger.info('Converting XML to HTML...')
        styledoc = etree.fromstring(xhtml)
        
        transform = etree.XSLT(styledoc)
        result = transform(doc)
        tdir = os.path.dirname(xml)
        html = os.path.join(tdir, 'index.html')
        f = open(html, 'wb')
        f.write(transform.tostring(result))
        f.close()
    finally:
        os.chdir(cwd)
    return html
            
if __name__ == '__main__':
    sys.exit(main())    
        