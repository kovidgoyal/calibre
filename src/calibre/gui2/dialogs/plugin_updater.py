#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import re, datetime, traceback
from lxml import html
from PyQt4.Qt import (Qt, QUrl, QFrame, QVBoxLayout, QLabel, QBrush, QTextEdit,
                      QComboBox, QAbstractItemView, QHBoxLayout, QDialogButtonBox,
                      QAbstractTableModel, QVariant, QTableView, QModelIndex,
                      QSortFilterProxyModel, QAction, QIcon, QDialog,
                      QFont, QPixmap, QSize)
from calibre import browser, prints
from calibre.constants import numeric_version, iswindows, isosx, DEBUG
from calibre.customize.ui import (initialized_plugins, is_disabled, remove_plugin,
                                  add_plugin, enable_plugin, disable_plugin,
                                  NameConflict, has_external_plugins)
from calibre.gui2 import error_dialog, question_dialog, info_dialog, NONE, open_url, gprefs
from calibre.gui2.preferences.plugins import ConfigWidget
from calibre.utils.date import UNDEFINED_DATE, format_date


MR_URL = 'http://www.mobileread.com/forums/'
MR_INDEX_URL = MR_URL + 'showpost.php?p=1362767&postcount=1'

FILTER_ALL = 0
FILTER_INSTALLED = 1
FILTER_UPDATE_AVAILABLE = 2
FILTER_NOT_INSTALLED = 3

def get_plugin_updates_available(raise_error=False):
    '''
    API exposed to read whether there are updates available for any
    of the installed user plugins.
    Returns None if no updates found
    Returns list(DisplayPlugin) of plugins installed that have a new version
    '''
    if not has_external_plugins():
        return None
    display_plugins = read_available_plugins(raise_error=raise_error)
    if display_plugins:
        update_plugins = filter(filter_upgradeable_plugins, display_plugins)
        if len(update_plugins) > 0:
            return update_plugins
    return None

def filter_upgradeable_plugins(display_plugin):
    return display_plugin.is_upgrade_available()

def filter_not_installed_plugins(display_plugin):
    return not display_plugin.is_installed()

def read_available_plugins(raise_error=False):
    display_plugins = []
    br = browser()
    br.set_handle_gzip(True)
    try:
        raw = br.open_novisit(MR_INDEX_URL).read()
        if not raw:
            return
    except:
        if raise_error:
            raise
        traceback.print_exc()
        return
    raw = raw.decode('utf-8', errors='replace')
    root = html.fromstring(raw)
    list_nodes = root.xpath('//div[@id="post_message_1362767"]/ul/li')
    # Add our deprecated plugins which are nested in a grey span
    list_nodes.extend(root.xpath('//div[@id="post_message_1362767"]/span/ul/li'))
    for list_node in list_nodes:
        try:
            display_plugin = DisplayPlugin(list_node)
            get_installed_plugin_status(display_plugin)
            display_plugins.append(display_plugin)
        except:
            if DEBUG:
                prints('======= MobileRead Parse Error =======')
                traceback.print_exc()
                prints(html.tostring(list_node))
    display_plugins = sorted(display_plugins, key=lambda k: k.name)
    return display_plugins

def get_installed_plugin_status(display_plugin):
    display_plugin.installed_version = None
    display_plugin.plugin = None
    for plugin in initialized_plugins():
        if plugin.name == display_plugin.name:
            display_plugin.plugin = plugin
            display_plugin.installed_version = plugin.version
            break
    if display_plugin.uninstall_plugins:
        # Plugin requires a specific plugin name to be uninstalled first
        # This could occur when a plugin is renamed (Kindle Collections)
        # or multiple plugins deprecated into a newly named one.
        # Check whether user has the previous version(s) installed
        plugins_to_remove = list(display_plugin.uninstall_plugins)
        for plugin_to_uninstall in plugins_to_remove:
            found = False
            for plugin in initialized_plugins():
                if plugin.name == plugin_to_uninstall:
                    found = True
                    break
            if not found:
                display_plugin.uninstall_plugins.remove(plugin_to_uninstall)


class ImageTitleLayout(QHBoxLayout):
    '''
    A reusable layout widget displaying an image followed by a title
    '''
    def __init__(self, parent, icon_name, title):
        QHBoxLayout.__init__(self)
        title_font = QFont()
        title_font.setPointSize(16)
        title_image_label = QLabel(parent)
        pixmap = QPixmap()
        pixmap.load(I(icon_name))
        if pixmap is None:
            error_dialog(parent, _('Restart required'),
                         _('You must restart Calibre before using this plugin!'), show=True)
        else:
            title_image_label.setPixmap(pixmap)
        title_image_label.setMaximumSize(32, 32)
        title_image_label.setScaledContents(True)
        self.addWidget(title_image_label)
        shelf_label = QLabel(title, parent)
        shelf_label.setFont(title_font)
        self.addWidget(shelf_label)
        self.insertStretch(-1)


class SizePersistedDialog(QDialog):
    '''
    This dialog is a base class for any dialogs that want their size/position
    restored when they are next opened.
    '''

    initial_extra_size = QSize(0, 0)

    def __init__(self, parent, unique_pref_name):
        QDialog.__init__(self, parent)
        self.unique_pref_name = unique_pref_name
        self.geom = gprefs.get(unique_pref_name, None)
        self.finished.connect(self.dialog_closing)

    def resize_dialog(self):
        if self.geom is None:
            self.resize(self.sizeHint()+self.initial_extra_size)
        else:
            self.restoreGeometry(self.geom)

    def dialog_closing(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom


class VersionHistoryDialog(SizePersistedDialog):

    def __init__(self, parent, plugin_name, html):
        SizePersistedDialog.__init__(self, parent, 'Plugin Updater plugin:version history dialog')
        self.setWindowTitle(_('Version History for %s')%plugin_name)

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.notes = QTextEdit(html, self)
        self.notes.setReadOnly(True)
        layout.addWidget(self.notes)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()


class PluginFilterComboBox(QComboBox):
    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        items = [_('All'), _('Installed'), _('Update available'), _('Not installed')]
        self.addItems(items)


class DisplayPlugin(object):

    def __init__(self, list_node):
        # The html from the index web page looks like this:
        '''
<li><a href="http://www.mobileread.com/forums/showthread.php?t=121787">Book Sync</a><br />
<i>Add books to a list to be automatically sent to your device the next time it is connected.<br />
<span class="resize_1">Version: 1.1; Released: 02-22-2011; Calibre: 0.7.42; Author: kiwidude; <br />
Platforms: Windows, OSX, Linux; History: Yes;</span></i></li>
        '''
        self.name = list_node.xpath('a')[0].text_content().strip()
        self.forum_link = list_node.xpath('a/@href')[0].strip()
        self.installed_version = None

        description_text = list_node.xpath('i')[0].text_content()
        description_parts = description_text.partition('Version:')
        self.description = description_parts[0].strip()

        details_text = description_parts[1] + description_parts[2].replace('\r\n','')
        details_pairs = details_text.split(';')
        details = {}
        for details_pair in details_pairs:
            pair = details_pair.split(':')
            if len(pair) == 2:
                key = pair[0].strip().lower()
                value = pair[1].strip()
                details[key] = value

        donation_node = list_node.xpath('i/span/a/@href')
        self.donation_link = donation_node[0] if donation_node else None

        self.available_version = self._version_text_to_tuple(details.get('version', None))

        release_date = details.get('released', '01-01-0101').split('-')
        date_parts = [int(re.search(r'(\d+)', x).group(1)) for x in release_date]
        self.release_date = datetime.date(date_parts[2], date_parts[0], date_parts[1])

        self.calibre_required_version = self._version_text_to_tuple(details.get('calibre', None))
        self.author = details.get('author', '')
        self.platforms = [p.strip().lower() for p in details.get('platforms', '').split(',')]
        # Optional pairing just for plugins which require checking for uninstall first
        self.uninstall_plugins = []
        uninstall = details.get('uninstall', None)
        if uninstall:
            self.uninstall_plugins = [i.strip() for i in uninstall.split(',')]
        self.has_changelog = details.get('history', 'No').lower() in ['yes', 'true']
        self.is_deprecated = details.get('deprecated', 'No').lower() in ['yes', 'true']

    def _version_text_to_tuple(self, version_text):
        if version_text:
            ver = version_text.split('.')
            while len(ver) < 3:
                ver.append('0')
            ver = [int(re.search(r'(\d+)', x).group(1)) for x in ver]
            return tuple(ver)
        else:
            return None

    def is_disabled(self):
        if self.plugin is None:
            return False
        return is_disabled(self.plugin)

    def is_installed(self):
        return self.installed_version is not None

    def is_upgrade_available(self):
        return self.is_installed() and (self.installed_version < self.available_version \
                or self.is_deprecated)

    def is_valid_platform(self):
        if iswindows:
            return 'windows' in self.platforms
        if isosx:
            return 'osx' in self.platforms
        return 'linux' in self.platforms

    def is_valid_calibre(self):
        return numeric_version >= self.calibre_required_version

    def is_valid_to_install(self):
        return self.is_valid_platform() and self.is_valid_calibre() and not self.is_deprecated


class DisplayPluginSortFilterModel(QSortFilterProxyModel):

    def __init__(self, parent):
        QSortFilterProxyModel.__init__(self, parent)
        self.setSortRole(Qt.UserRole)
        self.filter_criteria = FILTER_ALL

    def filterAcceptsRow(self, sourceRow, sourceParent):
        index = self.sourceModel().index(sourceRow, 0, sourceParent)
        display_plugin = self.sourceModel().display_plugins[index.row()]
        if self.filter_criteria == FILTER_ALL:
            return not (display_plugin.is_deprecated and not display_plugin.is_installed())
        if self.filter_criteria == FILTER_INSTALLED:
            return display_plugin.is_installed()
        if self.filter_criteria == FILTER_UPDATE_AVAILABLE:
            return display_plugin.is_upgrade_available()
        if self.filter_criteria == FILTER_NOT_INSTALLED:
            return not display_plugin.is_installed() and not display_plugin.is_deprecated
        return False

    def set_filter_criteria(self, filter_value):
        self.filter_criteria = filter_value
        self.invalidateFilter()


class DisplayPluginModel(QAbstractTableModel):

    def __init__(self, display_plugins):
        QAbstractTableModel.__init__(self)
        self.display_plugins = display_plugins
        self.headers = map(QVariant, [_('Plugin Name'), _('Donate'), _('Status'), _('Installed'),
                                      _('Available'), _('Released'), _('Calibre'), _('Author')])

    def rowCount(self, *args):
        return len(self.display_plugins)

    def columnCount(self, *args):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return NONE

    def data(self, index, role):
        if not index.isValid():
            return NONE;
        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount():
            return NONE
        display_plugin = self.display_plugins[row]
        if role in [Qt.DisplayRole, Qt.UserRole]:
            if col == 0:
                return QVariant(display_plugin.name)
            if col == 1:
                if display_plugin.donation_link:
                    return QVariant(_('PayPal'))
            if col == 2:
                return self._get_status(display_plugin)
            if col == 3:
                return QVariant(self._get_display_version(display_plugin.installed_version))
            if col == 4:
                return QVariant(self._get_display_version(display_plugin.available_version))
            if col == 5:
                if role == Qt.UserRole:
                    return self._get_display_release_date(display_plugin.release_date, 'yyyyMMdd')
                else:
                    return self._get_display_release_date(display_plugin.release_date)
            if col == 6:
                return QVariant(self._get_display_version(display_plugin.calibre_required_version))
            if col == 7:
                return QVariant(display_plugin.author)
        elif role == Qt.DecorationRole:
            if col == 0:
                return self._get_status_icon(display_plugin)
            if col == 1:
                if display_plugin.donation_link:
                    return QIcon(I('donate.png'))
        elif role == Qt.ToolTipRole:
            if col == 1 and display_plugin.donation_link:
                return QVariant(_('This plugin is FREE but you can reward the developer for their effort\n'
                                  'by donating to them via PayPal.\n\n'
                                  'Right-click and choose Donate to reward: ')+display_plugin.author)
            else:
                return self._get_status_tooltip(display_plugin)
        elif role == Qt.ForegroundRole:
            if col != 1: # Never change colour of the donation column
                if display_plugin.is_deprecated:
                    return QVariant(QBrush(Qt.blue))
                if display_plugin.is_disabled():
                    return QVariant(QBrush(Qt.gray))
        return NONE

    def plugin_to_index(self, display_plugin):
        for i, p in enumerate(self.display_plugins):
            if display_plugin == p:
                return self.index(i, 0, QModelIndex())
        return QModelIndex()

    def refresh_plugin(self, display_plugin):
        idx = self.plugin_to_index(display_plugin)
        self.dataChanged.emit(idx, idx)

    def _get_display_release_date(self, date_value, format='dd MMM yyyy'):
        if date_value and date_value != UNDEFINED_DATE:
            return QVariant(format_date(date_value, format))
        return NONE

    def _get_display_version(self, version):
        if version is None:
            return ''
        return '.'.join([str(v) for v in list(version)])

    def _get_status(self, display_plugin):
        if not display_plugin.is_valid_platform():
            return _('Platform unavailable')
        if not display_plugin.is_valid_calibre():
            return _('Calibre upgrade required')
        if display_plugin.is_installed():
            if display_plugin.is_deprecated:
                return _('Plugin deprecated')
            elif display_plugin.is_upgrade_available():
                return _('New version available')
            else:
                return _('Latest version installed')
        return _('Not installed')

    def _get_status_icon(self, display_plugin):
        if display_plugin.is_deprecated:
            icon_name = 'plugin_deprecated.png'
        elif display_plugin.is_disabled():
            if display_plugin.is_upgrade_available():
                if display_plugin.is_valid_to_install():
                    icon_name = 'plugin_disabled_valid.png'
                else:
                    icon_name = 'plugin_disabled_invalid.png'
            else:
                icon_name = 'plugin_disabled_ok.png'
        elif display_plugin.is_installed():
            if display_plugin.is_upgrade_available():
                if display_plugin.is_valid_to_install():
                    icon_name = 'plugin_upgrade_valid.png'
                else:
                    icon_name = 'plugin_upgrade_invalid.png'
            else:
                icon_name = 'plugin_upgrade_ok.png'
        else: # A plugin available not currently installed
            if display_plugin.is_valid_to_install():
                icon_name = 'plugin_new_valid.png'
            else:
                icon_name = 'plugin_new_invalid.png'
        return QIcon(I('plugins/' + icon_name))

    def _get_status_tooltip(self, display_plugin):
        if display_plugin.is_deprecated:
            return QVariant(_('This plugin has been deprecated and should be uninstalled')+'\n\n'+
                            _('Right-click to see more options'))
        if not display_plugin.is_valid_platform():
            return QVariant(_('This plugin can only be installed on: %s') % \
                            ', '.join(display_plugin.platforms)+'\n\n'+
                            _('Right-click to see more options'))
        if numeric_version < display_plugin.calibre_required_version:
            return QVariant(_('You must upgrade to at least Calibre %s before installing this plugin') % \
                            self._get_display_version(display_plugin.calibre_required_version)+'\n\n'+
                            _('Right-click to see more options'))
        if display_plugin.installed_version < display_plugin.available_version:
            if display_plugin.installed_version is None:
                return QVariant(_('You can install this plugin')+'\n\n'+
                                _('Right-click to see more options'))
            else:
                return QVariant(_('A new version of this plugin is available')+'\n\n'+
                                _('Right-click to see more options'))
        return QVariant(_('This plugin is installed and up-to-date')+'\n\n'+
                        _('Right-click to see more options'))


class PluginUpdaterDialog(SizePersistedDialog):

    initial_extra_size = QSize(350, 100)

    def __init__(self, gui, initial_filter=FILTER_UPDATE_AVAILABLE):
        SizePersistedDialog.__init__(self, gui, 'Plugin Updater plugin:plugin updater dialog')
        self.gui = gui
        self.forum_link = None
        self.model = None
        self.do_restart = False
        self._initialize_controls()
        self._create_context_menu()

        display_plugins = read_available_plugins()

        if display_plugins:
            self.model = DisplayPluginModel(display_plugins)
            self.proxy_model = DisplayPluginSortFilterModel(self)
            self.proxy_model.setSourceModel(self.model)
            self.plugin_view.setModel(self.proxy_model)
            self.plugin_view.resizeColumnsToContents()
            self.plugin_view.selectionModel().currentRowChanged.connect(self._plugin_current_changed)
            self.plugin_view.doubleClicked.connect(self.install_button.click)
            self.filter_combo.setCurrentIndex(initial_filter)
            self._select_and_focus_view()
        else:
            error_dialog(self.gui, _('Update Check Failed'),
                        _('Unable to reach the MobileRead plugins forum index page.'),
                        det_msg=MR_INDEX_URL, show=True)
            self.filter_combo.setEnabled(False)
        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _initialize_controls(self):
        self.setWindowTitle(_('User plugins'))
        self.setWindowIcon(QIcon(I('plugins/plugin_updater.png')))
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        title_layout = ImageTitleLayout(self, 'plugins/plugin_updater.png',
                _('User Plugins'))
        layout.addLayout(title_layout)

        header_layout = QHBoxLayout()
        layout.addLayout(header_layout)
        self.filter_combo = PluginFilterComboBox(self)
        self.filter_combo.setMinimumContentsLength(20)
        self.filter_combo.currentIndexChanged[int].connect(self._filter_combo_changed)
        header_layout.addWidget(QLabel(_('Filter list of plugins')+':', self))
        header_layout.addWidget(self.filter_combo)
        header_layout.addStretch(10)

        self.plugin_view = QTableView(self)
        self.plugin_view.horizontalHeader().setStretchLastSection(True)
        self.plugin_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.plugin_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.plugin_view.setAlternatingRowColors(True)
        self.plugin_view.setSortingEnabled(True)
        self.plugin_view.setIconSize(QSize(28, 28))
        layout.addWidget(self.plugin_view)

        details_layout = QHBoxLayout()
        layout.addLayout(details_layout)
        forum_label = QLabel('<a href="http://www.foo.com/">Plugin Forum Thread</a>', self)
        forum_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
        forum_label.linkActivated.connect(self._forum_label_activated)
        details_layout.addWidget(QLabel(_('Description')+':', self), 0, Qt.AlignLeft)
        details_layout.addWidget(forum_label, 1, Qt.AlignRight)

        self.description = QLabel(self)
        self.description.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.description.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.description.setMinimumHeight(40)
        layout.addWidget(self.description)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        self.finished.connect(self._finished)
        self.install_button = self.button_box.addButton(_('&Install'), QDialogButtonBox.AcceptRole)
        self.install_button.setToolTip(_('Install the selected plugin'))
        self.install_button.clicked.connect(self._install_clicked)
        self.install_button.setEnabled(False)
        self.configure_button = self.button_box.addButton(' '+_('&Customize plugin ')+' ', QDialogButtonBox.ResetRole)
        self.configure_button.setToolTip(_('Customize the options for this plugin'))
        self.configure_button.clicked.connect(self._configure_clicked)
        self.configure_button.setEnabled(False)
        layout.addWidget(self.button_box)

    def _create_context_menu(self):
        self.plugin_view.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.install_action = QAction(QIcon(I('plugins/plugin_upgrade_ok.png')), _('&Install'), self)
        self.install_action.setToolTip(_('Install the selected plugin'))
        self.install_action.triggered.connect(self._install_clicked)
        self.install_action.setEnabled(False)
        self.plugin_view.addAction(self.install_action)
        self.history_action = QAction(QIcon(I('chapters.png')), _('Version &History'), self)
        self.history_action.setToolTip(_('Show history of changes to this plugin'))
        self.history_action.triggered.connect(self._history_clicked)
        self.history_action.setEnabled(False)
        self.plugin_view.addAction(self.history_action)
        self.forum_action = QAction(QIcon(I('plugins/mobileread.png')), _('Plugin &Forum Thread'), self)
        self.forum_action.triggered.connect(self._forum_label_activated)
        self.forum_action.setEnabled(False)
        self.plugin_view.addAction(self.forum_action)

        sep1 = QAction(self)
        sep1.setSeparator(True)
        self.plugin_view.addAction(sep1)

        self.toggle_enabled_action = QAction(_('Enable/&Disable plugin'), self)
        self.toggle_enabled_action.setToolTip(_('Enable or disable this plugin'))
        self.toggle_enabled_action.triggered.connect(self._toggle_enabled_clicked)
        self.toggle_enabled_action.setEnabled(False)
        self.plugin_view.addAction(self.toggle_enabled_action)
        self.uninstall_action = QAction(_('&Remove plugin'), self)
        self.uninstall_action.setToolTip(_('Uninstall the selected plugin'))
        self.uninstall_action.triggered.connect(self._uninstall_clicked)
        self.uninstall_action.setEnabled(False)
        self.plugin_view.addAction(self.uninstall_action)

        sep2 = QAction(self)
        sep2.setSeparator(True)
        self.plugin_view.addAction(sep2)

        self.donate_enabled_action = QAction(QIcon(I('donate.png')), _('Donate to developer'), self)
        self.donate_enabled_action.setToolTip(_('Donate to the developer of this plugin'))
        self.donate_enabled_action.triggered.connect(self._donate_clicked)
        self.donate_enabled_action.setEnabled(False)
        self.plugin_view.addAction(self.donate_enabled_action)

        sep3 = QAction(self)
        sep3.setSeparator(True)
        self.plugin_view.addAction(sep3)

        self.configure_action = QAction(QIcon(I('config.png')), _('&Customize plugin'), self)
        self.configure_action.setToolTip(_('Customize the options for this plugin'))
        self.configure_action.triggered.connect(self._configure_clicked)
        self.configure_action.setEnabled(False)
        self.plugin_view.addAction(self.configure_action)

    def _finished(self, *args):
        if self.model:
            update_plugins = filter(filter_upgradeable_plugins, self.model.display_plugins)
            self.gui.recalc_update_label(len(update_plugins))

    def _plugin_current_changed(self, current, previous):
        if current.isValid():
            actual_idx = self.proxy_model.mapToSource(current)
            display_plugin = self.model.display_plugins[actual_idx.row()]
            self.description.setText(display_plugin.description)
            self.forum_link = display_plugin.forum_link
            self.forum_action.setEnabled(bool(self.forum_link))
            self.install_button.setEnabled(display_plugin.is_valid_to_install())
            self.install_action.setEnabled(self.install_button.isEnabled())
            self.uninstall_action.setEnabled(display_plugin.is_installed())
            self.history_action.setEnabled(display_plugin.has_changelog)
            self.configure_button.setEnabled(display_plugin.is_installed())
            self.configure_action.setEnabled(self.configure_button.isEnabled())
            self.toggle_enabled_action.setEnabled(display_plugin.is_installed())
            self.donate_enabled_action.setEnabled(bool(display_plugin.donation_link))
        else:
            self.description.setText('')
            self.forum_link = None
            self.forum_action.setEnabled(False)
            self.install_button.setEnabled(False)
            self.install_action.setEnabled(False)
            self.uninstall_action.setEnabled(False)
            self.history_action.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.configure_action.setEnabled(False)
            self.toggle_enabled_action.setEnabled(False)
            self.donate_enabled_action.setEnabled(False)

    def _donate_clicked(self):
        plugin = self._selected_display_plugin()
        if plugin and plugin.donation_link:
            open_url(QUrl(plugin.donation_link))

    def _select_and_focus_view(self, change_selection=True):
        if change_selection and self.plugin_view.model().rowCount() > 0:
            self.plugin_view.selectRow(0)
        else:
            idx = self.plugin_view.selectionModel().currentIndex()
            self._plugin_current_changed(idx, 0)
        self.plugin_view.setFocus()

    def _filter_combo_changed(self, idx):
        self.proxy_model.set_filter_criteria(idx)
        if idx == FILTER_NOT_INSTALLED:
            self.plugin_view.sortByColumn(5, Qt.DescendingOrder)
        else:
            self.plugin_view.sortByColumn(0, Qt.AscendingOrder)
        self._select_and_focus_view()

    def _forum_label_activated(self):
        if self.forum_link:
            open_url(QUrl(self.forum_link))

    def _selected_display_plugin(self):
        idx = self.plugin_view.selectionModel().currentIndex()
        actual_idx = self.proxy_model.mapToSource(idx)
        return self.model.display_plugins[actual_idx.row()]

    def _uninstall_plugin(self, name_to_remove):
        if DEBUG:
            prints('Removing plugin: ', name_to_remove)
        remove_plugin(name_to_remove)
        # Make sure that any other plugins that required this plugin
        # to be uninstalled first have the requirement removed
        for display_plugin in self.model.display_plugins:
            # Make sure we update the status and display of the
            # plugin we just uninstalled
            if name_to_remove in display_plugin.uninstall_plugins:
                if DEBUG:
                    prints('Removing uninstall dependency for: ', display_plugin.name)
                display_plugin.uninstall_plugins.remove(name_to_remove)
            if display_plugin.name == name_to_remove:
                if DEBUG:
                    prints('Resetting plugin to uninstalled status: ', display_plugin.name)
                display_plugin.installed_version = None
                display_plugin.plugin = None
                display_plugin.uninstall_plugins = []
                if self.proxy_model.filter_criteria not in [FILTER_INSTALLED, FILTER_UPDATE_AVAILABLE]:
                    self.model.refresh_plugin(display_plugin)

    def _uninstall_clicked(self):
        display_plugin = self._selected_display_plugin()
        if not question_dialog(self, _('Are you sure?'), '<p>'+
                   _('Are you sure you want to uninstall the <b>%s</b> plugin?')%display_plugin.name,
                   show_copy_button=False):
            return
        self._uninstall_plugin(display_plugin.name)
        if self.proxy_model.filter_criteria in [FILTER_INSTALLED, FILTER_UPDATE_AVAILABLE]:
            self.model.reset()
            self._select_and_focus_view()
        else:
            self._select_and_focus_view(change_selection=False)

    def _install_clicked(self):
        display_plugin = self._selected_display_plugin()
        if not question_dialog(self, _('Install %s')%display_plugin.name, '<p>' + \
                _('Installing plugins is a <b>security risk</b>. '
                'Plugins can contain a virus/malware. '
                    'Only install it if you got it from a trusted source.'
                    ' Are you sure you want to proceed?'),
                show_copy_button=False):
            return

        if display_plugin.uninstall_plugins:
            uninstall_names = list(display_plugin.uninstall_plugins)
            if DEBUG:
                prints('Uninstalling plugin: ', ', '.join(uninstall_names))
            for name_to_remove in uninstall_names:
                self._uninstall_plugin(name_to_remove)

        if DEBUG:
            prints('Locating zip file for %s: %s'% (display_plugin.name, display_plugin.forum_link))
        self.gui.status_bar.showMessage(
                _('Locating zip file for %(name)s: %(link)s') % dict(
                    name=display_plugin.name, link=display_plugin.forum_link))
        plugin_zip_url = self._read_zip_attachment_url(display_plugin.forum_link)
        if not plugin_zip_url:
            return error_dialog(self.gui, _('Install Plugin Failed'),
                        _('Unable to locate a plugin zip file for <b>%s</b>') % display_plugin.name,
                        det_msg=display_plugin.forum_link, show=True)

        if DEBUG:
            prints('Downloading plugin zip attachment: ', plugin_zip_url)
        self.gui.status_bar.showMessage(_('Downloading plugin zip attachment: %s') % plugin_zip_url)
        zip_path = self._download_zip(plugin_zip_url)

        if DEBUG:
            prints('Installing plugin: ', zip_path)
        self.gui.status_bar.showMessage(_('Installing plugin: %s') % zip_path)

        do_restart = False
        try:
            try:
                plugin = add_plugin(zip_path)
            except NameConflict as e:
                return error_dialog(self.gui, _('Already exists'),
                        unicode(e), show=True)
            # Check for any toolbars to add to.
            widget = ConfigWidget(self.gui)
            widget.gui = self.gui
            widget.check_for_add_to_toolbars(plugin)
            self.gui.status_bar.showMessage(_('Plugin installed: %s') % display_plugin.name)
            d = info_dialog(self.gui, _('Success'),
                    _('Plugin <b>{0}</b> successfully installed under <b>'
                        ' {1} plugins</b>. You may have to restart calibre '
                        'for the plugin to take effect.').format(plugin.name, plugin.type),
                    show_copy_button=False)
            b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
            b.setIcon(QIcon(I('lt.png')))
            d.do_restart = False
            def rf():
                d.do_restart = True
            b.clicked.connect(rf)
            d.set_details('')
            d.exec_()
            b.clicked.disconnect()
            do_restart = d.do_restart

            display_plugin.plugin = plugin
            # We cannot read the 'actual' version information as the plugin will not be loaded yet
            display_plugin.installed_version = display_plugin.available_version
        except:
            if DEBUG:
                prints('ERROR occurred while installing plugin: %s'%display_plugin.name)
                traceback.print_exc()
            error_dialog(self.gui, _('Install Plugin Failed'),
                         _('A problem occurred while installing this plugin.'
                           ' This plugin will now be uninstalled.'
                           ' Please post the error message in details below into'
                           ' the forum thread for this plugin and restart Calibre.'),
                         det_msg=traceback.format_exc(), show=True)
            if DEBUG:
                prints('Due to error now uninstalling plugin: %s'%display_plugin.name)
                remove_plugin(display_plugin.name)
                display_plugin.plugin = None

        display_plugin.uninstall_plugins = []
        if self.proxy_model.filter_criteria in [FILTER_NOT_INSTALLED, FILTER_UPDATE_AVAILABLE]:
            self.model.reset()
            self._select_and_focus_view()
        else:
            self.model.refresh_plugin(display_plugin)
            self._select_and_focus_view(change_selection=False)
        if do_restart:
            self.do_restart = True
            self.accept()

    def _history_clicked(self):
        display_plugin = self._selected_display_plugin()
        text = self._read_version_history_html(display_plugin.forum_link)
        if text:
            dlg = VersionHistoryDialog(self, display_plugin.name, text)
            dlg.exec_()
        else:
            return error_dialog(self, _('Version history missing'),
                _('Unable to find the version history for %s')%display_plugin.name,
                show=True)

    def _configure_clicked(self):
        display_plugin = self._selected_display_plugin()
        plugin = display_plugin.plugin
        if not plugin.is_customizable():
            return info_dialog(self, _('Plugin not customizable'),
                _('Plugin: %s does not need customization')%plugin.name, show=True)
        from calibre.customize import InterfaceActionBase
        if isinstance(plugin, InterfaceActionBase) and not getattr(plugin,
                'actual_iaction_plugin_loaded', False):
            return error_dialog(self, _('Must restart'),
                    _('You must restart calibre before you can'
                        ' configure the <b>%s</b> plugin')%plugin.name, show=True)
        plugin.do_user_config(self.parent())

    def _toggle_enabled_clicked(self):
        display_plugin = self._selected_display_plugin()
        plugin = display_plugin.plugin
        if not plugin.can_be_disabled:
            return error_dialog(self,_('Plugin cannot be disabled'),
                         _('The plugin: %s cannot be disabled')%plugin.name, show=True)
        if is_disabled(plugin):
            enable_plugin(plugin)
        else:
            disable_plugin(plugin)
        self.model.refresh_plugin(display_plugin)

    def _read_version_history_html(self, forum_link):
        br = browser()
        br.set_handle_gzip(True)
        try:
            raw = br.open_novisit(forum_link).read()
            if not raw:
                return None
        except:
            traceback.print_exc()
            return None
        raw = raw.decode('utf-8', errors='replace')
        root = html.fromstring(raw)
        spoiler_nodes = root.xpath('//div[@class="smallfont" and strong="Spoiler"]')
        for spoiler_node in spoiler_nodes:
            try:
                if spoiler_node.getprevious() is None:
                    # This is a spoiler node that has been indented using [INDENT]
                    # Need to go up to parent div, then previous node to get header
                    heading_node = spoiler_node.getparent().getprevious()
                else:
                    # This is a spoiler node after a BR tag from the heading
                    heading_node = spoiler_node.getprevious().getprevious()
                if heading_node is None:
                    continue
                if heading_node.text_content().lower().find('version history') != -1:
                    div_node = spoiler_node.xpath('div')[0]
                    text = html.tostring(div_node, method='html', encoding=unicode)
                    return re.sub('<div\s.*?>', '<div>', text)
            except:
                if DEBUG:
                    prints('======= MobileRead Parse Error =======')
                    traceback.print_exc()
                    prints(html.tostring(spoiler_node))
        return None

    def _read_zip_attachment_url(self, forum_link):
        br = browser()
        br.set_handle_gzip(True)
        try:
            raw = br.open_novisit(forum_link).read()
            if not raw:
                return None
        except:
            traceback.print_exc()
            return None
        raw = raw.decode('utf-8', errors='replace')
        root = html.fromstring(raw)
        attachment_nodes = root.xpath('//fieldset/table/tr/td/a')
        for attachment_node in attachment_nodes:
            try:
                filename = attachment_node.text_content().lower()
                if filename.find('.zip') != -1:
                    full_url = MR_URL + attachment_node.attrib['href']
                    return full_url
            except:
                if DEBUG:
                    prints('======= MobileRead Parse Error =======')
                    traceback.print_exc()
                    prints(html.tostring(attachment_node))
        return None

    def _download_zip(self, plugin_zip_url):
        from calibre.ptempfile import PersistentTemporaryFile
        br = browser()
        br.set_handle_gzip(True)
        raw = br.open_novisit(plugin_zip_url).read()
        pt = PersistentTemporaryFile('.zip')
        pt.write(raw)
        pt.close()
        return pt.name
