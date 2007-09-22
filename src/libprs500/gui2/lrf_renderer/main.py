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
''''''

import sys, logging, os, traceback

from PyQt4.QtGui import QApplication, QKeySequence, QPainter
from PyQt4.QtCore import Qt, QObject, SIGNAL, QCoreApplication, QThread

from libprs500 import __appname__, __version__, __author__, setup_cli_handlers, islinux
from libprs500.ebooks.lrf.parser import LRFDocument

from libprs500.gui2 import ORG_NAME, APP_UID
from libprs500.gui2.dialogs.conversion_error import ConversionErrorDialog
from libprs500.gui2.lrf_renderer.main_ui import Ui_MainWindow
from libprs500.gui2.main_window import MainWindow
from libprs500.gui2.lrf_renderer.document import Document

class RenderWorker(QThread):
    
    def __init__(self, parent, lrf_stream, logger, opts):
        QThread.__init__(self, parent)
        self.stream, self.logger, self.opts = lrf_stream, logger, opts
        self.lrf = None
        self.document = None
        self.exception = None
        
    def run(self):
        try:
            self.lrf = LRFDocument(self.stream)
            self.stream.close()
            self.stream = None            
        except Exception, err:
            self.exception = err
            self.formatted_traceback = traceback.format_exc()
        self.emit(SIGNAL('parsed()'))
        
class Main(QObject, Ui_MainWindow, MainWindow):
    def __init__(self, window, stream, logger, opts):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)        
        self.setupUi(window)
        self.window = window
        self.logger = logger
        self.file_name = os.path.basename(stream.name) if hasattr(stream, 'name') else ''
        self.opts = opts
        self.document = None
        self.renderer = RenderWorker(self, stream, logger, opts)
        QObject.connect(self.renderer, SIGNAL('parsed()'), self.parsed, Qt.QueuedConnection)
        self.document = Document(self.logger, self.opts)
        QObject.connect(self.document, SIGNAL('chapter_rendered(int)'), self.chapter_rendered)
        QObject.connect(self.document, SIGNAL('page_changed(PyQt_PyObject)'), self.page_changed)
        
        self.search.help_text = 'Search'
        self.search.clear_to_help()
        
        self.action_next_page.setShortcuts(QKeySequence.MoveToNextPage)
        self.action_previous_page.setShortcuts(QKeySequence.MoveToPreviousPage)
        QObject.connect(self.action_next_page, SIGNAL('triggered(bool)'), self.next) 
        QObject.connect(self.action_previous_page, SIGNAL('triggered(bool)'), self.previous)
        QObject.connect(self.action_back, SIGNAL('triggered(bool)'), self.back)
        QObject.connect(self.action_forward, SIGNAL('triggered(bool)'), self.forward)
        QObject.connect(self.spin_box, SIGNAL('valueChanged(int)'), self.go_to_page)
        QObject.connect(self.slider, SIGNAL('valueChanged(int)'), self.go_to_page)
        self.next_button.setDefaultAction(self.action_next_page)
        self.previous_button.setDefaultAction(self.action_previous_page)
        self.back_button.setDefaultAction(self.action_back)
        self.forward_button.setDefaultAction(self.action_forward)
        
        self.graphics_view.setRenderHint(QPainter.Antialiasing, True)
        self.graphics_view.setRenderHint(QPainter.TextAntialiasing, True)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
    def page_changed(self, num):
        self.slider.setValue(num)
        self.spin_box.setValue(num)
    
    def render(self):
        self.stack.setCurrentIndex(1)
        self.renderer.start()
    
    
    def parsed(self, *args):
        if self.renderer.lrf is not None:
            self.graphics_view.setMinimumSize(self.renderer.lrf.device_info.width+5, 
                                              self.renderer.lrf.device_info.height)
            self.window.setWindowTitle(self.renderer.lrf.metadata.title + ' - ' + __appname__)
            self.document_title = self.renderer.lrf.metadata.title
            if self.opts.profile:
                import cProfile
                render, lrf = self.document.render, self.renderer.lrf
                cProfile.runctx('render(lrf)', globals(), locals(), lrf.metadata.title+'.stats')
                print 'Stats written to', self.renderer.lrf.metadata.title+'.stats'
            else:
                self.document.render(self.renderer.lrf)
            self.renderer.lrf = None
            self.graphics_view.setScene(self.document)
            self.graphics_view.show()
            self.spin_box.setRange(1, self.document.num_of_pages)
            self.slider.setRange(1, self.document.num_of_pages)
            self.spin_box.setSuffix(' of %d'%(self.document.num_of_pages,))
            self.spin_box.updateGeometry()
            self.stack.setCurrentIndex(0)
        else:
            exception = self.renderer.exception
            print >>sys.stderr, 'Error rendering document'
            print >>sys.stderr, exception
            print >>sys.stderr, self.renderer.formatted_traceback
            msg =  u'<p><b>%s</b>: '%(exception.__class__.__name__,) + unicode(str(exception), 'utf8', 'replace') + u'</p>'
            msg += u'<p>Failed to render document</p>'
            msg += u'<p>Detailed <b>traceback</b>:<pre>'
            msg += self.renderer.formatted_traceback + '</pre>'            
            d = ConversionErrorDialog(self.window, 'Error while rendering file', msg)
            d.exec_()
            
    def chapter_rendered(self, num):
        if num > 0:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(num)
            self.progress_bar.setValue(0)
            self.progress_label.setText('Rendering '+ self.document_title)
        else:
            self.progress_bar.setValue(self.progress_bar.value()+1)
        QCoreApplication.processEvents()
    
    def next(self, triggered):
        self.document.next()
        
    def previous(self, triggered):
        self.document.previous()
        
    def go_to_page(self, num):
        self.document.show_page(num)
        
    def forward(self, triggered):
        self.document.forward()
    
    def back(self, triggered):
        self.document.back()


def file_renderer(stream, logger, opts):
    from PyQt4.Qt import QMainWindow
    window = QMainWindow()
    window.setAttribute(Qt.WA_DeleteOnClose)
    window.setWindowTitle(__appname__ + ' - LRF Viewer')
    return Main(window, stream, logger, opts)
    

def option_parser():
    from optparse import OptionParser
    parser = OptionParser(usage='%prog book.lrf', version=__appname__+' '+__version__,
                          epilog='Created by ' + __author__)
    parser.add_option('--verbose', default=False, action='store_true', dest='verbose',
                      help='Print more information about the rendering process')
    parser.add_option('--visual-debug', help='Turn on visual aids to debugging the rendering engine',
                      default=False, action='store_true', dest='visual_debug')
    parser.add_option('--disable-hyphenation', dest='hyphenate', default=True, action='store_false',
                      help='Disable hyphenation. Should significantly speed up rendering.')
    parser.add_option('--profile', dest='profile', default='False', action='store_true',
                      help='Profile the LRf renderer')
    return parser

def main(args=sys.argv, logger=None):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    if logger is None:
        level = logging.DEBUG if opts.verbose else logging.INFO
        logger = logging.getLogger('lrf2lrs')
        setup_cli_handlers(logger, level)
    pid = os.fork() if False and islinux else -1
    if pid <= 0:
        app = QApplication(args)
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setApplicationName(APP_UID)
        main = file_renderer(open(args[1], 'rb'), logger, opts)
        sys.excepthook = main.unhandled_exception
        main.window.show()
        main.render()
        return app.exec_()        
    return 0

if __name__ == '__main__':
    sys.exit(main())
    
    