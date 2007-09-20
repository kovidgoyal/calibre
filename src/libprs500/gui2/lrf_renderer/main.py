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

import sys, logging, os

from PyQt4.Qt import QApplication, QCoreApplication
from PyQt4.QtCore import Qt, QObject

from libprs500 import __appname__, __version__, __author__, setup_cli_handlers, islinux
from libprs500.ebooks.lrf.parser import LRFDocument

from libprs500.gui2 import ORG_NAME, APP_UID
from libprs500.gui2.lrf_renderer.main_ui import Ui_MainWindow
from libprs500.gui2.lrf_renderer.document import Document

class Main(QObject, Ui_MainWindow):
    def __init__(self, window, stream, logger, opts):
        QObject.__init__(self)
        Ui_MainWindow.__init__(self)        
        self.setupUi(window)
        self.window = window
        self.logger = logger
        self.file_name = os.path.basename(stream.name) if hasattr(stream, 'name') else ''
        self.stream = stream
        self.opts = opts
        
    def render(self):
        self.window.show()
        self.statusbar.showMessage('Parsing LRF file '+self.file_name)
        QCoreApplication.instance().processEvents()
        self.lrf = LRFDocument(self.stream)
        self.stream.close()
        self.stream = None
        self.graphics_view.resize(self.lrf.device_info.width+15, self.lrf.device_info.height)
        self.window.setWindowTitle(self.lrf.metadata.title + ' - ' + __appname__)
        self.statusbar.showMessage('Building graphical representation')
        QCoreApplication.instance().processEvents()
        
        
        self.document = Document(self.lrf, self.logger, self.opts)
        self.graphics_view.setScene(self.document)
        self.graphics_view.show()
        self.statusbar.clearMessage()
        QCoreApplication.instance().processEvents()
        self.document.next() 

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
        main.render()
        return app.exec_()        
    return 0

if __name__ == '__main__':
    sys.exit(main())