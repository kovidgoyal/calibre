__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Convert .txt files to .lrf
"""
import os, sys, codecs, logging, re, shutil

from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks import ConversionError
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre.ebooks.markdown import markdown
from calibre import setup_cli_handlers
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFCreator

def option_parser():
    parser = lrf_option_parser(
_('''%prog [options] mybook.txt


%prog converts mybook.txt to mybook.lrf'''))
    parser.add_option('--debug-html-generation', action='store_true', default=False,
                      dest='debug_html_generation', help=_('Print generated HTML to stdout and quit.'))
    return parser
    
def fix_image_includes(sdir, tdir, match):
    path = match.group(1).split('/')
    src = os.path.join(sdir, *path)
    dest = os.path.join(tdir, *path)
    p = os.path.dirname(dest)
    if not os.path.exists(p):
        os.makedirs(p)
    if not os.path.exists(dest):
        shutil.copyfile(src, dest)
    

def generate_html(txtfile, encoding, tdir):
    '''
    Convert txtfile to html and return a PersistentTemporaryFile object pointing
    to the file with the HTML.
    '''
    txtfile = os.path.abspath(txtfile)
    enc = encoding
    if not encoding:
        encodings = ['cp1252', 'latin-1', 'utf8', 'iso-8859-1', 'koi8_r', 'koi8_u']
        txt, enc = None, None
        for encoding in encodings:
            try:
                txt = codecs.open(txtfile, 'rb', encoding).read()
            except UnicodeDecodeError:
                continue
            enc = encoding
            break
        if txt == None:
            raise ConversionError, 'Could not detect encoding of %s'%(txtfile,)
    else:
        txt = codecs.open(txtfile, 'rb', enc).read()
    
    print 'Converting text to HTML...'
    md = markdown.Markdown(
                       extensions=['footnotes', 'tables', 'toc'],
                       safe_mode=False,
                       )
    html = '<html><body>'+md.convert(txt)+'</body></html>'
    for match in re.finditer(r'<img\s+[^>]*src="([^"]+)"', html):
        fix_image_includes(os.path.dirname(txtfile), tdir, match)
    p = os.path.join(tdir, 'index.html')
    open(p, 'wb').write(html.encode('utf-8'))
    mi = MetaInformation(os.path.splitext(os.path.basename(txtfile))[0], [_('Unknown')])
    opf = OPFCreator(tdir, mi)
    opf.create_manifest([(os.path.join(tdir, 'index.html'), None)])
    opf.create_spine([os.path.join(tdir, 'index.html')])
    opf.render(open(os.path.join(tdir, 'metadata.opf'), 'wb'))
    return p
        
def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('txt2lrf')
        setup_cli_handlers(logger, level)
    txt = os.path.abspath(os.path.expanduser(path))
    if not hasattr(options, 'debug_html_generation'):
        options.debug_html_generation = False
    tdir = PersistentTemporaryDirectory('_txt2lrf')
    htmlfile = generate_html(txt, options.encoding, tdir)
    options.encoding = 'utf-8'
    if not options.debug_html_generation:
        options.force_page_break = 'h2'
        if not options.output:
            ext = '.lrs' if options.lrs else '.lrf'
            options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
        options.output = os.path.abspath(os.path.expanduser(options.output))
        if not options.title:
            options.title = os.path.splitext(os.path.basename(path))[0]
        html_process_file(htmlfile, options, logger)
    else:
        print open(htmlfile, 'rb').read()        

def main(args=sys.argv, logger=None):
    parser = option_parser()    
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No txt file specified'
        return 1
    process_file(args[1], options, logger)
    return 0

if __name__ == '__main__':
    sys.exit(main())
