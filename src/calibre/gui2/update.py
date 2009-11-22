__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback

from PyQt4.QtCore import QObject, SIGNAL, QTimer
import mechanize

from calibre.constants import __version__, iswindows, isosx
from calibre import browser

URL = 'http://status.calibre-ebook.com/latest'

class CheckForUpdates(QObject):

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.timer = QTimer(self)
        self.first = True
        self.connect(self.timer, SIGNAL('timeout()'), self)
        self.start = self.timer.start
        self.stop = self.timer.stop

    def __call__(self):
        if self.first:
            self.timer.setInterval(1000*24*60*60)
            self.first = False

        try:
            br = browser()
            req = mechanize.Request(URL)
            req.add_header('CALIBRE_VERSION', __version__)
            req.add_header('CALIBRE_OS',
                    'win' if iswindows else 'osx' if isosx else 'oth')
            version = br.open(req).read().strip()
            if version and version != __version__:
                self.emit(SIGNAL('update_found(PyQt_PyObject)'), version)
        except:
            traceback.print_exc()

