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

import StringIO, traceback, sys

from PyQt4.QtGui import QMainWindow
from libprs500.gui2.dialogs.conversion_error import ConversionErrorDialog

class MainWindow(QMainWindow):
    
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
    
    def unhandled_exception(self, type, value, tb):
        sio = StringIO.StringIO()
        traceback.print_exception(type, value, tb, file=sio)
        fe = sio.getvalue()
        print >>sys.stderr, fe
        msg = '<p><b>' + unicode(str(value), 'utf8', 'replace') + '</b></p>'
        msg += '<p>Detailed <b>traceback</b>:<pre>'+fe+'</pre>'
        d = ConversionErrorDialog(self, 'ERROR: Unhandled exception', msg)
        d.exec_()