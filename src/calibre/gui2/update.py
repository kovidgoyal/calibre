__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback

from PyQt4.QtCore import QThread, pyqtSignal
import mechanize

from calibre.constants import __version__, iswindows, isosx
from calibre import browser
from calibre.utils.config import prefs

URL = 'http://status.calibre-ebook.com/latest'

class CheckForUpdates(QThread):

    update_found = pyqtSignal(object)
    INTERVAL = 24*60*60

    def __init__(self, parent):
        QThread.__init__(self, parent)

    def run(self):
        while True:
            try:
                br = browser()
                req = mechanize.Request(URL)
                req.add_header('CALIBRE_VERSION', __version__)
                req.add_header('CALIBRE_OS',
                        'win' if iswindows else 'osx' if isosx else 'oth')
                req.add_header('CALIBRE_INSTALL_UUID', prefs['installation_uuid'])
                version = br.open(req).read().strip()
                if version and version != __version__:
                    self.update_found.emit(version)
            except:
                traceback.print_exc()
            self.sleep(self.INTERVAL)

