'''
Write content to PDF.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'

import os, logging, shutil, sys

from calibre import LoggingInterface
from calibre.ebooks.epub.iterator import SpineItem
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.customize.ui import run_plugins_on_postprocess
from calibre.utils.config import Config, StringConfig

from PyQt4 import QtCore
from PyQt4.Qt import QUrl, QEventLoop, SIGNAL, QObject, QApplication, QPrinter, \
    QMetaObject, Qt
from PyQt4.QtWebKit import QWebView

from pyPdf import PdfFileWriter, PdfFileReader
    
class PDFWriter(QObject):
    def __init__(self):
        if QApplication.instance() is None:
            QApplication([])
        QObject.__init__(self)
        
        self.logger = logging.getLogger('oeb2pdf')
        
        self.loop = QEventLoop()
        self.view = QWebView()
        self.connect(self.view, SIGNAL('loadFinished(bool)'), self._render_html)
        self.render_queue = []
        self.combine_queue = []
        self.tmp_path = PersistentTemporaryDirectory('_any2pdf_parts')

    def dump(self, oebpath, path):
        self._delete_tmpdir()
        
        opf = OPF(oebpath, os.path.dirname(oebpath))
        self.render_queue = [SpineItem(i.path) for i in opf.spine]
        self.combine_queue = []
        self.path = path
        
        QMetaObject.invokeMethod(self, "_render_book", Qt.QueuedConnection)
        self.loop.exec_()
        
    @QtCore.pyqtSignature('_render_book()')
    def _render_book(self):
        if len(self.render_queue) == 0:
            self._write()
        else:
            self._render_next()
            
    def _render_next(self):
        item = str(self.render_queue.pop(0))        
        self.combine_queue.append(os.path.join(self.tmp_path, '%s.pdf' % os.path.basename(item)))
        
        self.logger.info('Processing %s...' % item)
    
        self.view.load(QUrl(item))

    def _render_html(self, ok):
        if ok:
            item_path = os.path.join(self.tmp_path, '%s.pdf' % os.path.basename(str(self.view.url().toLocalFile())))
            
            self.logger.debug('\tRendering item as %s' % item_path)
        
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageMargins(1, 1, 1, 1, QPrinter.Inch)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(item_path)
            self.view.print_(printer)
        self._render_book()

    def _delete_tmpdir(self):
        if os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, True)
            self.tmp_path = PersistentTemporaryDirectory('_any2pdf_parts')

    def _write(self):
        self.logger.info('Combining individual PDF parts...')
    
        try:
            outPDF = PdfFileWriter()
            for item in self.combine_queue:
                inputPDF = PdfFileReader(file(item, 'rb'))
                for page in inputPDF.pages:
                    outPDF.addPage(page)
            outputStream = file(self.path, 'wb')
            outPDF.write(outputStream)
            outputStream.close()
        finally:
            self._delete_tmpdir()
            self.loop.exit(0)


def config(defaults=None):
    desc = _('Options to control the conversion to PDF')
    if defaults is None:
        c = Config('pdf', desc)
    else:
        c = StringConfig(defaults, desc)
        
    pdf = c.add_group('PDF', _('PDF options.'))
    
    return c
    

def option_parser():
    c = config()
    parser = c.option_parser(usage='%prog '+_('[options]')+' file.opf')
    parser.add_option(
        '-o', '--output', default=None, 
        help=_('Output file. Default is derived from input filename.'))
    parser.add_option(
        '-v', '--verbose', default=0, action='count',
        help=_('Useful for debugging.'))
    return parser

def oeb2pdf(opts, inpath):
    logger = LoggingInterface(logging.getLogger('oeb2pdf'))
    logger.setup_cli_handler(opts.verbose)
    
    outpath = opts.output
    if outpath is None:
        outpath = os.path.basename(inpath)
        outpath = os.path.splitext(outpath)[0] + '.pdf'

    writer = PDFWriter()
    writer.dump(inpath, outpath)
    run_plugins_on_postprocess(outpath, 'pdf')
    logger.log_info(_('Output written to ') + outpath)
    
def main(argv=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(argv[1:])
    if len(args) != 1:
        parser.print_help()
        return 1
    inpath = args[0]
    retval = oeb2pdf(opts, inpath)
    return retval

if __name__ == '__main__':
    sys.exit(main())
    
