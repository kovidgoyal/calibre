__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback

from PyQt4.Qt import QThread, pyqtSignal, Qt, QUrl
import mechanize

from calibre.constants import __appname__, __version__, iswindows, isosx
from calibre import browser
from calibre.utils.config import prefs
from calibre.gui2 import config, dynamic, question_dialog, open_url

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

class UpdateMixin(object):

    def __init__(self, opts):
        if not opts.no_update_check:
            self.update_checker = CheckForUpdates(self)
            self.update_checker.update_found.connect(self.update_found,
                    type=Qt.QueuedConnection)
            self.update_checker.start()

    def update_found(self, version):
        os = 'windows' if iswindows else 'osx' if isosx else 'linux'
        url = 'http://calibre-ebook.com/download_%s'%os
        self.status_bar.new_version_available(version, url)

        if config.get('new_version_notification') and \
                dynamic.get('update to version %s'%version, True):
            if question_dialog(self, _('Update available'),
                    _('%s has been updated to version %s. '
                    'See the <a href="http://calibre-ebook.com/whats-new'
                    '">new features</a>. Visit the download pa'
                    'ge?')%(__appname__, version)):
                url = 'http://calibre-ebook.com/download_'+\
                    ('windows' if iswindows else 'osx' if isosx else 'linux')
                open_url(QUrl(url))
            dynamic.set('update to version %s'%version, False)



