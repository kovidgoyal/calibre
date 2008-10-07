__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''''''

import sys, os, subprocess, logging
from functools import partial
from calibre import isosx, setup_cli_handlers, filename_to_utf8, iswindows, islinux
from calibre.ebooks import ConversionError, DRMError
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.ebooks.lrf import option_parser as lrf_option_parser
from calibre.ebooks.lrf.html.convert_from import process_file as html_process_file
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.metadata.pdf import get_metadata

PDFTOHTML = 'pdftohtml'
popen = subprocess.Popen
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)
if iswindows and hasattr(sys, 'frozen'):
    PDFTOHTML = os.path.join(os.path.dirname(sys.executable), 'pdftohtml.exe')
    popen = partial(subprocess.Popen, creationflags=0x08) # CREATE_NO_WINDOW=0x08 so that no ugly console is popped up
if islinux and getattr(sys, 'frozen_path', False):
    PDFTOHTML = os.path.join(getattr(sys, 'frozen_path'), 'pdftohtml')

def generate_html(pathtopdf, tdir):
    '''
    Convert the pdf into html.
    @return: Path to a temporary file containing the HTML.
    '''
    if isinstance(pathtopdf, unicode):
        pathtopdf = pathtopdf.encode(sys.getfilesystemencoding())
    if not os.access(pathtopdf, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtopdf
    index = os.path.join(tdir, 'index.html')
    # This is neccessary as pdftohtml doesn't always (linux) respect absolute paths
    pathtopdf = os.path.abspath(pathtopdf)
    cmd = (PDFTOHTML, '-enc', 'UTF-8',  '-noframes',  '-p',  '-nomerge', pathtopdf, os.path.basename(index))
    cwd = os.getcwd()
    
    try:
        os.chdir(tdir)
        try:
            p = popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        except OSError, err:
            if err.errno == 2:
                raise ConversionError(_('Could not find pdftohtml, check it is in your PATH'), True)
            else:
                raise
        print p.stdout.read()
        ret = p.wait()
        if ret != 0:
            err = p.stderr.read()
            raise ConversionError, err
        if not os.path.exists(index) or os.stat(index).st_size < 100:
            raise DRMError()
        
        raw = open(index, 'rb').read()
        open(index, 'wb').write('<!-- created by calibre\'s pdftohtml -->\n'+raw)
        if not '<br' in raw[:4000]:
            raise ConversionError(os.path.basename(pathtopdf) + _(' is an image based PDF. Only conversion of text based PDFs is supported.'), True)
        try:
            mi = get_metadata(open(pathtopdf, 'rb'))
        except:
            mi = MetaInformation(None, None)
        if not mi.title:
            mi.title = os.path.splitext(os.path.basename(pathtopdf))[0]
        if not mi.authors:
            mi.authors = [_('Unknown')]
        opf = OPFCreator(tdir, mi)
        opf.create_manifest([('index.html', None)])
        opf.create_spine(['index.html'])
        opf.render(open('metadata.opf', 'wb'))
    finally:
        os.chdir(cwd)
    return index

def option_parser():
    return lrf_option_parser(
_('''%prog [options] mybook.pdf


%prog converts mybook.pdf to mybook.lrf''')
        )

def process_file(path, options, logger=None):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('pdf2lrf')
        setup_cli_handlers(logger, level)
    pdf = os.path.abspath(os.path.expanduser(path))
    tdir = PersistentTemporaryDirectory('_pdf2lrf')
    htmlfile = generate_html(pdf, tdir)
    if not options.output:
        ext = '.lrs' if options.lrs else '.lrf'        
        options.output = os.path.abspath(os.path.basename(os.path.splitext(path)[0]) + ext)
    else:
        options.output = os.path.abspath(options.output)
    options.pdftohtml = True
    if not options.title:
        options.title = filename_to_utf8(os.path.splitext(os.path.basename(options.output))[0])
    html_process_file(htmlfile, options, logger)


def main(args=sys.argv, logger=None):
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
