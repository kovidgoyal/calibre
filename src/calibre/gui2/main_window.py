__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import StringIO, traceback, sys

from PyQt4.Qt import QMainWindow, QString, Qt, QFont
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre import OptionParser

def option_parser(usage='''\
Usage: %prog [options]

Launch the Graphical User Interface
'''):
    parser = OptionParser(usage)
    parser.add_option('--redirect-console-output', default=False, action='store_true', dest='redirect',
                      help=_('Redirect console output to a dialog window (both stdout and stderr). Useful on windows where GUI apps do not have a output streams.'))
    return parser

class DebugWindow(ConversionErrorDialog):
    
    def __init__(self, parent):
        ConversionErrorDialog.__init__(self, parent, 'Console output', '')
        self.setModal(Qt.NonModal)
        font = QFont()
        font.setStyleHint(QFont.TypeWriter)
        self.text.setFont(font)
        
    def write(self, msg):
        self.text.setPlainText(self.text.toPlainText()+QString(msg))
        
    def flush(self):
        pass    

class MainWindow(QMainWindow):
    
    def __init__(self, opts, parent=None):
        QMainWindow.__init__(self, parent)
        if getattr(opts, 'redirect', False):
            self.__console_redirect = DebugWindow(self)
            sys.stdout = sys.stderr = self.__console_redirect
            self.__console_redirect.show()
            print 'testing 1'
            print 'testing 2'
    
    def unhandled_exception(self, type, value, tb):
        try:
            sio = StringIO.StringIO()
            traceback.print_exception(type, value, tb, file=sio)
            fe = sio.getvalue()
            print >>sys.stderr, fe
            msg = '<p><b>' + unicode(str(value), 'utf8', 'replace') + '</b></p>'
            msg += '<p>Detailed <b>traceback</b>:<pre>'+fe+'</pre>'
            d = ConversionErrorDialog(self, _('ERROR: Unhandled exception'), msg)
            d.exec_()
        except:
            pass