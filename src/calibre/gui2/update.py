__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import traceback

from PyQt4.Qt import QThread, pyqtSignal, Qt, QUrl, QDialog, QGridLayout, \
        QLabel, QCheckBox, QDialogButtonBox, QIcon, QPixmap
import mechanize

from calibre.constants import __appname__, __version__, iswindows, isosx
from calibre import browser
from calibre.utils.config import prefs
from calibre.gui2 import config, dynamic, open_url

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
                if version and version != __version__ and len(version) < 10:
                    self.update_found.emit(version)
            except:
                traceback.print_exc()
            self.sleep(self.INTERVAL)

class UpdateNotification(QDialog):

    def __init__(self, version, parent=None):
        QDialog.__init__(self, parent)
        self.resize(400, 250)
        self.l = QGridLayout()
        self.setLayout(self.l)
        self.logo = QLabel()
        self.logo.setMaximumWidth(110)
        self.logo.setPixmap(QPixmap(I('lt.png')).scaled(100, 100,
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        self.label = QLabel('<p>'+
            _('%s has been updated to version <b>%s</b>. '
            'See the <a href="http://calibre-ebook.com/whats-new'
            '">new features</a>. Visit the download pa'
            'ge?')%(__appname__, version))
        self.label.setOpenExternalLinks(True)
        self.label.setWordWrap(True)
        self.setWindowTitle(_('Update available!'))
        self.setWindowIcon(QIcon(I('lt.png')))
        self.l.addWidget(self.logo, 0, 0)
        self.l.addWidget(self.label, 0, 1)
        self.cb = QCheckBox(
            _('Show this notification for future updates'), self)
        self.l.addWidget(self.cb, 1, 0, 1, -1)
        self.cb.setChecked(config.get('new_version_notification'))
        self.cb.stateChanged.connect(self.show_future)
        self.bb = QDialogButtonBox(self)
        b = self.bb.addButton(_('&Get update'), self.bb.AcceptRole)
        b.setDefault(True)
        b.setIcon(QIcon(I('arrow-down.png')))
        self.bb.addButton(self.bb.Cancel)
        self.l.addWidget(self.bb, 2, 0, 1, -1)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        dynamic.set('update to version %s'%version, False)

    def show_future(self, *args):
        config.set('new_version_notification', bool(self.cb.isChecked()))

    def accept(self):
        url = 'http://calibre-ebook.com/download_'+\
            ('windows' if iswindows else 'osx' if isosx else 'linux')
        open_url(QUrl(url))

        QDialog.accept(self)

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
            self._update_notification__ = UpdateNotification(version,
                    parent=self)
            self._update_notification__.show()


