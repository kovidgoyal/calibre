__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''''''

import sys, os, subprocess, logging
from libprs500 import isosx, setup_cli_handlers, filename_to_utf8
from libprs500.ebooks import ConversionError
from libprs500.ptempfile import PersistentTemporaryDirectory
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks.lrf.html.convert_from import process_file as html_process_file

PDFTOHTML = 'pdftohtml'
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOHTML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOHTML)


def generate_html(pathtopdf, logger):
    '''
    Convert the pdf into html.
    @return: Path to a temporary file containing the HTML.
    '''
    if not os.access(pathtopdf, os.R_OK):
        raise ConversionError, 'Cannot read from ' + pathtopdf
    tdir = PersistentTemporaryDirectory('pdftohtml')
    index = os.path.join(tdir, 'index.html')
    # This is neccessary as pdftohtml doesn't always (linux) respect absolute paths
    cmd = PDFTOHTML + ' -enc UTF-8 -noframes -p -nomerge "%s" "%s"'%(pathtopdf, os.path.basename(index))
    cwd = os.getcwd()
    
    try:
        os.chdir(tdir)
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, 
                             stdout=subprocess.PIPE)
        logger.info(p.stdout.read())
        ret = p.wait()
        if ret != 0:
            err = p.stderr.read()
            raise ConversionError, err
        if os.stat(index).st_size < 100:
            raise ConversionError(os.path.basename(pathtopdf) + ' does not allow copying of text.')
    finally:
        os.chdir(cwd)
    return index

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