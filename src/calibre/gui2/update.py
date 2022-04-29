__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import re
import ssl
from qt.core import (
    QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QIcon, QLabel, QObject, Qt,
    QUrl, pyqtSignal
)
from threading import Event, Thread

from calibre import as_unicode, prints
from calibre.constants import (
    __appname__, __version__, ismacos, isportable, iswindows, numeric_version
)
from calibre.gui2 import config, dynamic, icon_resource_manager, open_url
from calibre.gui2.dialogs.plugin_updater import get_plugin_updates_available
from calibre.utils.config import prefs
from calibre.utils.https import get_https_resource_securely
from calibre.utils.localization import localize_website_link
from calibre.utils.serialize import msgpack_dumps, msgpack_loads
from polyglot.binary import as_hex_unicode, from_hex_bytes

URL = 'https://code.calibre-ebook.com/latest'
# URL = 'http://localhost:8000/latest'
NO_CALIBRE_UPDATE = (0, 0, 0)


def get_download_url():
    which = ('portable' if isportable else 'windows' if iswindows
            else 'osx' if ismacos else 'linux')
    return localize_website_link('https://calibre-ebook.com/download_' + which)


def get_newest_version():
    icon_theme_name = icon_resource_manager.user_theme_name
    if icon_theme_name == 'default':
        icon_theme_name = ''
    headers={
        'CALIBRE-VERSION':__version__,
        'CALIBRE-OS': ('win' if iswindows else 'osx' if ismacos else 'oth'),
        'CALIBRE-INSTALL-UUID': prefs['installation_uuid'],
        'CALIBRE-ICON-THEME': icon_theme_name,
    }
    try:
        version = get_https_resource_securely(URL, headers=headers)
    except ssl.SSLError as err:
        if getattr(err, 'reason', None) != 'CERTIFICATE_VERIFY_FAILED':
            raise
        # certificate verification failed, since the version check contains no
        # critical information, ignore and proceed
        # We have to do this as if the calibre CA certificate ever
        # needs to be revoked, then we won't be able to do version checks
        version = get_https_resource_securely(URL, headers=headers, cacerts=None)
    try:
        version = version.decode('utf-8').strip()
    except UnicodeDecodeError:
        version = ''
    ans = NO_CALIBRE_UPDATE
    m = re.match(r'(\d+)\.(\d+).(\d+)$', version)
    if m is not None:
        ans = tuple(map(int, (m.group(1), m.group(2), m.group(3))))
    return ans


class Signal(QObject):

    update_found = pyqtSignal(object, object)


class CheckForUpdates(Thread):

    INTERVAL = 24*60*60  # seconds
    daemon = True

    def __init__(self, parent):
        Thread.__init__(self, name='CheckForUpdates')
        self.shutdown_event = Event()
        self.signal = Signal(parent)

    def run(self):
        while not self.shutdown_event.is_set():
            calibre_update_version = NO_CALIBRE_UPDATE
            plugins_update_found = 0
            try:
                version = get_newest_version()
                if version[:2] > numeric_version[:2]:
                    calibre_update_version = version
            except Exception as e:
                prints('Failed to check for calibre update:', as_unicode(e))
            try:
                update_plugins = get_plugin_updates_available(raise_error=True)
                if update_plugins is not None:
                    plugins_update_found = len(update_plugins)
            except Exception as e:
                prints('Failed to check for plugin update:', as_unicode(e))
            if calibre_update_version != NO_CALIBRE_UPDATE or plugins_update_found > 0:
                self.signal.update_found.emit(calibre_update_version, plugins_update_found)
            self.shutdown_event.wait(self.INTERVAL)

    def shutdown(self):
        self.shutdown_event.set()


def version_key(calibre_version):
    if isinstance(calibre_version, bytes):
        calibre_version = calibre_version.decode('utf-8')
    if calibre_version.count('.') > 1:
        calibre_version = calibre_version.rpartition('.')[0]
    return calibre_version


def is_version_notified(calibre_version):
    key = version_key(calibre_version)
    done = dynamic.get('notified-version-updates') or set()
    return key in done


def save_version_notified(calibre_version):
    done = dynamic.get('notified-version-updates') or set()
    done.add(version_key(calibre_version))
    dynamic.set('notified-version-updates', done)


class UpdateNotification(QDialog):

    def __init__(self, calibre_version, plugin_updates, parent=None):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.resize(400, 250)
        self.l = QGridLayout()
        self.setLayout(self.l)
        self.logo = QLabel()
        self.logo.setMaximumWidth(110)
        self.logo.setPixmap(QIcon.ic('lt.png').pixmap(100, 100))
        ver = calibre_version
        if ver.endswith('.0'):
            ver = ver[:-2]
        self.label = QLabel('<p>'+ _(
            'New version <b>{ver}</b> of {app} is available for download. '
            'See the <a href="{url}">new features</a>.').format(
                url=localize_website_link('https://calibre-ebook.com/whats-new'),
                app=__appname__, ver=ver))
        self.label.setOpenExternalLinks(True)
        self.label.setWordWrap(True)
        self.setWindowTitle(_('Update available!'))
        self.setWindowIcon(QIcon.ic('lt.png'))
        self.l.addWidget(self.logo, 0, 0)
        self.l.addWidget(self.label, 0, 1)
        self.cb = QCheckBox(
            _('Show this notification for future updates'), self)
        self.l.addWidget(self.cb, 1, 0, 1, -1)
        self.cb.setChecked(config.get('new_version_notification'))
        self.cb.stateChanged.connect(self.show_future)
        self.bb = QDialogButtonBox(self)
        b = self.bb.addButton(_('&Get update'), QDialogButtonBox.ButtonRole.AcceptRole)
        b.setDefault(True)
        b.setIcon(QIcon.ic('arrow-down.png'))
        if plugin_updates > 0:
            b = self.bb.addButton(_('Update &plugins'), QDialogButtonBox.ButtonRole.ActionRole)
            b.setIcon(QIcon.ic('plugins/plugin_updater.png'))
            b.clicked.connect(self.get_plugins, type=Qt.ConnectionType.QueuedConnection)
        self.bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.l.addWidget(self.bb, 2, 0, 1, -1)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        save_version_notified(calibre_version)

    def get_plugins(self):
        from calibre.gui2.dialogs.plugin_updater import (
            FILTER_UPDATE_AVAILABLE, PluginUpdaterDialog
        )
        d = PluginUpdaterDialog(self.parent(),
                initial_filter=FILTER_UPDATE_AVAILABLE)
        d.exec()
        if d.do_restart:
            QDialog.accept(self)
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            if gui is not None:
                gui.quit(restart=True)

    def show_future(self, *args):
        config.set('new_version_notification', bool(self.cb.isChecked()))

    def accept(self):
        open_url(QUrl(get_download_url()))

        QDialog.accept(self)


class UpdateMixin:

    def __init__(self, *args, **kw):
        pass

    def init_update_mixin(self, opts):
        self.last_newest_calibre_version = NO_CALIBRE_UPDATE
        if not opts.no_update_check:
            self.update_checker = CheckForUpdates(self)
            self.update_checker.signal.update_found.connect(self.update_found,
                    type=Qt.ConnectionType.QueuedConnection)
            self.update_checker.start()

    def recalc_update_label(self, number_of_plugin_updates):
        self.update_found(self.last_newest_calibre_version, number_of_plugin_updates)

    def update_found(self, calibre_version, number_of_plugin_updates, force=False, no_show_popup=False):
        self.last_newest_calibre_version = calibre_version
        has_calibre_update = calibre_version != NO_CALIBRE_UPDATE and calibre_version[0] > 0
        has_plugin_updates = number_of_plugin_updates > 0
        self.plugin_update_found(number_of_plugin_updates)
        version_url = as_hex_unicode(msgpack_dumps((calibre_version, number_of_plugin_updates)))
        calibre_version = '.'.join(map(str, calibre_version))

        if not has_calibre_update and not has_plugin_updates:
            self.status_bar.update_label.setVisible(False)
            return
        if has_calibre_update:
            plt = ''
            if has_plugin_updates:
                plt = ngettext(' and one plugin update', ' and {} plugin updates', number_of_plugin_updates).format(number_of_plugin_updates)
            msg = ('<span style="color:green; font-weight: bold">%s: '
                    '<a href="update:%s">%s%s</a></span>') % (
                        _('Update found'), version_url, calibre_version, plt)
        else:
            plt = ngettext('plugin update available', 'plugin updates available', number_of_plugin_updates)
            msg = ('<a href="update:%s">%d %s</a>')%(version_url, number_of_plugin_updates, plt)
        self.status_bar.update_label.setText(msg)
        self.status_bar.update_label.setVisible(True)

        if has_calibre_update:
            if (force or (config.get('new_version_notification') and not is_version_notified(calibre_version))):
                if not no_show_popup:
                    self._update_notification__ = UpdateNotification(calibre_version,
                            number_of_plugin_updates, parent=self)
                    self._update_notification__.show()
        elif has_plugin_updates:
            if force:
                from calibre.gui2.dialogs.plugin_updater import (
                    FILTER_UPDATE_AVAILABLE, PluginUpdaterDialog
                )
                d = PluginUpdaterDialog(self,
                        initial_filter=FILTER_UPDATE_AVAILABLE)
                d.exec()
                if d.do_restart:
                    self.quit(restart=True)

    def plugin_update_found(self, number_of_updates):
        # Change the plugin icon to indicate there are updates available
        plugin = self.iactions.get('Plugin Updater', None)
        if not plugin:
            return
        if number_of_updates:
            plugin.qaction.setText(_('Plugin updates')+'*')
            plugin.qaction.setIcon(QIcon.ic('plugins/plugin_updater_updates.png'))
            plugin.qaction.setToolTip(
                ngettext('A plugin update is available',
                         'There are {} plugin updates available', number_of_updates).format(number_of_updates))
        else:
            plugin.qaction.setText(_('Plugin updates'))
            plugin.qaction.setIcon(QIcon.ic('plugins/plugin_updater.png'))
            plugin.qaction.setToolTip(_('Install and configure user plugins'))

    def update_link_clicked(self, url):
        url = str(url)
        if url.startswith('update:'):
            calibre_version, number_of_plugin_updates = msgpack_loads(from_hex_bytes(url[len('update:'):]))
            self.update_found(calibre_version, number_of_plugin_updates, force=True)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    UpdateNotification('x.y.z', False).exec()
    del app
