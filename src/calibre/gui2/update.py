__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback

from PyQt4.QtCore import QThread, SIGNAL
import mechanize

from calibre.constants import __version__
from calibre import browser

URL = 'http://status.calibre-ebook.com/latest'

class CheckForUpdates(QThread):

    def run(self):
        try:
            br = browser()
            req = mechanize.Request(URL)
            req.add_header('CALIBRE_VERSION', __version__)
            version = br.open(req).read().strip()
            if version and version != __version__:
                self.emit(SIGNAL('update_found(PyQt_PyObject)'), version)
        except:
            traceback.print_exc()

