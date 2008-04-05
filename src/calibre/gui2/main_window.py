__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import StringIO, traceback, sys

from PyQt4.QtGui import QMainWindow
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog

class MainWindow(QMainWindow):
    
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
    
    def unhandled_exception(self, type, value, tb):
        try:
            sio = StringIO.StringIO()
            traceback.print_exception(type, value, tb, file=sio)
            fe = sio.getvalue()
            print >>sys.stderr, fe
            msg = '<p><b>' + unicode(str(value), 'utf8', 'replace') + '</b></p>'
            msg += '<p>Detailed <b>traceback</b>:<pre>'+fe+'</pre>'
            d = ConversionErrorDialog(self, 'ERROR: Unhandled exception', msg)
            d.exec_()
        except:
            pass