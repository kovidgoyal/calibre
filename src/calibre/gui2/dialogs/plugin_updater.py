#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import datetime
import re
import traceback
from qt.core import (
    QAbstractItemView, QAbstractTableModel, QAction, QApplication, QBrush, QComboBox,
    QDialog, QDialogButtonBox, QFont, QFrame, QHBoxLayout, QIcon, QLabel, QLineEdit,
    QModelIndex, QPixmap, QSize, QSortFilterProxyModel, Qt, QTableView, QUrl,
    QVBoxLayout
)

from calibre import prints
from calibre.constants import (
    DEBUG, __appname__, __version__, ismacos, iswindows, numeric_version
)
from calibre.customize import PluginInstallationType
from calibre.customize.ui import (
    NameConflict, add_plugin, disable_plugin, enable_plugin, has_external_plugins,
    initialized_plugins, is_disabled, remove_plugin
)
from calibre.gui2 import error_dialog, gprefs, info_dialog, open_url, question_dialog
from calibre.gui2.preferences.plugins import ConfigWidget
from calibre.utils.date import UNDEFINED_DATE, format_date
from calibre.utils.https import get_https_resource_securely
from polyglot.builtins import itervalues

SERVER = 'https://code.calibre-ebook.com/plugins/'
INDEX_URL = '%splugins.json.bz2' % SERVER
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
        update_plugins = list(filter(filter_upgradeable_plugins, display_plugins))
        if len(update_plugins) > 0:
            return update_plugins
    return None


def filter_upgradeable_plugins(display_plugin):
    return display_plugin.installation_type is PluginInstallationType.EXTERNAL \
            and display_plugin.is_upgrade_available()


def filter_not_installed_plugins(display_plugin):
    return not display_plugin.is_installed()


def read_available_plugins(raise_error=False):
    import bz2
    import json
    display_plugins = []
    try:
        raw = get_https_resource_securely(INDEX_URL)
        if not raw:
            return
        raw = json.loads(bz2.decompress(raw))
    except:
        if raise_error:
            raise
        traceback.print_exc()
        return
    for plugin in itervalues(raw):
        try:
            display_plugin = DisplayPlugin(plugin)
            get_installed_plugin_status(display_plugin)
            display_plugins.append(display_plugin)
        except:
            if DEBUG:
                prints('======= Plugin Parse Error =======')
                traceback.print_exc()
                import pprint
                pprint.pprint(plugin)
    display_plugins = sorted(display_plugins, key=lambda k: k.name)
    return display_plugins


def get_installed_plugin_status(display_plugin):
    display_plugin.installed_version = None
    display_plugin.plugin = None
    for plugin in initialized_plugins():
        if plugin.name == display_plugin.qname \
                and plugin.installation_type is not PluginInstallationType.BUILTIN:
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
                         _('You must restart calibre before using this plugin!'), show=True)
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
            QApplication.instance().safe_restore_geometry(self, self.geom)

    def dialog_closing(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom


class PluginFilterComboBox(QComboBox):

    def __init__(self, parent):
        QComboBox.__init__(self, parent)
        items = [_('All'), _('Installed'), _('Update available'), _('Not installed')]
        self.addItems(items)


class DisplayPlugin:

    def __init__(self, plugin):
        self.name = plugin['index_name']
        self.qname = plugin.get('name', self.name)
        self.forum_link = plugin['thread_url']
        self.zip_url = SERVER + plugin['file']
        self.installed_version = None
        self.description = plugin['description']
        self.donation_link = plugin['donate']
        self.available_version = tuple(plugin['version'])
        self.release_date = datetime.datetime(*tuple(map(int, re.split(r'\D', plugin['last_modified'])))[:6]).date()
        self.calibre_required_version = tuple(plugin['minimum_calibre_version'])
        self.author = plugin['author']
        self.platforms = plugin['supported_platforms']
        self.uninstall_plugins = plugin['uninstall'] or []
        self.has_changelog = plugin['history']
        self.is_deprecated = plugin['deprecated']
        self.installation_type = PluginInstallationType.EXTERNAL

    def is_disabled(self):
        if self.plugin is None:
            return False
        return is_disabled(self.plugin)

    def is_installed(self):
        return self.installed_version is not None

    def name_matches_filter(self, filter_text):
        # filter_text is already lowercase @set_filter_text
        return filter_text in icu_lower(self.name)  # case-insensitive filtering

    def is_upgrade_available(self):
        if isinstance(self.installed_version, str):
            return True
        return self.is_installed() and (self.installed_version < self.available_version or self.is_deprecated)

    def is_valid_platform(self):
        if iswindows:
            return 'windows' in self.platforms
        if ismacos:
            return 'osx' in self.platforms
        return 'linux' in self.platforms

    def is_valid_calibre(self):
        return numeric_version >= self.calibre_required_version

    def is_valid_to_install(self):
        return self.is_valid_platform() and self.is_valid_calibre() and not self.is_deprecated


class DisplayPluginSortFilterModel(QSortFilterProxyModel):

    def __init__(self, parent):
        QSortFilterProxyModel.__init__(self, parent)
        self.setSortRole(Qt.ItemDataRole.UserRole)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.filter_criteria = FILTER_ALL
        self.filter_text = ""

    def filterAcceptsRow(self, sourceRow, sourceParent):
        index = self.sourceModel().index(sourceRow, 0, sourceParent)
        display_plugin = self.sourceModel().display_plugins[index.row()]
        if self.filter_criteria == FILTER_ALL:
            return not (display_plugin.is_deprecated and not display_plugin.is_installed()) and display_plugin.name_matches_filter(self.filter_text)
        if self.filter_criteria == FILTER_INSTALLED:
            return display_plugin.is_installed() and display_plugin.name_matches_filter(self.filter_text)
        if self.filter_criteria == FILTER_UPDATE_AVAILABLE:
            return display_plugin.is_upgrade_available() and display_plugin.name_matches_filter(self.filter_text)
        if self.filter_criteria == FILTER_NOT_INSTALLED:
            return not display_plugin.is_installed() and not display_plugin.is_deprecated and display_plugin.name_matches_filter(self.filter_text)
        return False

    def set_filter_criteria(self, filter_value):
        self.filter_criteria = filter_value
        self.invalidateFilter()

    def set_filter_text(self, filter_text_value):
        self.filter_text = icu_lower(str(filter_text_value))
        self.invalidateFilter()


class DisplayPluginModel(QAbstractTableModel):

    def __init__(self, display_plugins):
        QAbstractTableModel.__init__(self)
        self.display_plugins = display_plugins
        self.headers = list(map(str, [_('Plugin name'), _('Donate'), _('Status'), _('Installed'),
                                      _('Available'), _('Released'), _('calibre'), _('Author')]))

    def rowCount(self, *args):
        return len(self.display_plugins)

    def columnCount(self, *args):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount():
            return None
        display_plugin = self.display_plugins[row]
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]:
            if col == 0:
                return display_plugin.name
            if col == 1:
                if display_plugin.donation_link:
                    return _('PayPal')
            if col == 2:
                return self._get_status(display_plugin)
            if col == 3:
                return self._get_display_version(display_plugin.installed_version)
            if col == 4:
                return self._get_display_version(display_plugin.available_version)
            if col == 5:
                if role == Qt.ItemDataRole.UserRole:
                    return self._get_display_release_date(display_plugin.release_date, 'yyyyMMdd')
                else:
                    return self._get_display_release_date(display_plugin.release_date)
            if col == 6:
                return self._get_display_version(display_plugin.calibre_required_version)
            if col == 7:
                return display_plugin.author
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 0:
                return self._get_status_icon(display_plugin)
            if col == 1:
                if display_plugin.donation_link:
                    return QIcon.ic('donate.png')
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 1 and display_plugin.donation_link:
                return _('This plugin is FREE but you can reward the developer for their effort\n'
                                  'by donating to them via PayPal.\n\n'
                                  'Right-click and choose Donate to reward: ')+display_plugin.author
            else:
                return self._get_status_tooltip(display_plugin)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col != 1:  # Never change colour of the donation column
                if display_plugin.is_deprecated:
                    return QBrush(Qt.GlobalColor.blue)
                if display_plugin.is_disabled():
                    return QBrush(Qt.GlobalColor.gray)
        return None

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
            return format_date(date_value, format)
        return None

    def _get_display_version(self, version):
        if version is None:
            return ''
        return '.'.join([str(v) for v in list(version)])

    def _get_status(self, display_plugin):
        if not display_plugin.is_valid_platform():
            return _('Platform unavailable')
        if not display_plugin.is_valid_calibre():
            return _('calibre upgrade required')
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
        else:  # A plugin available not currently installed
            if display_plugin.is_valid_to_install():
                icon_name = 'plugin_new_valid.png'
            else:
                icon_name = 'plugin_new_invalid.png'
        return QIcon(I('plugins/' + icon_name))

    def _get_status_tooltip(self, display_plugin):
        if display_plugin.is_deprecated:
            return (_('This plugin has been deprecated and should be uninstalled')+'\n\n'+
                            _('Right-click to see more options'))
        if not display_plugin.is_valid_platform():
            return (_('This plugin can only be installed on: %s') %
                            ', '.join(display_plugin.platforms)+'\n\n'+
                            _('Right-click to see more options'))
        if numeric_version < display_plugin.calibre_required_version:
            return (_('You must upgrade to at least calibre %s before installing this plugin') %
                            self._get_display_version(display_plugin.calibre_required_version)+'\n\n'+
                            _('Right-click to see more options'))
        if display_plugin.installed_version is None:
            return (_('You can install this plugin')+'\n\n'+
                            _('Right-click to see more options'))
        try:
            if display_plugin.installed_version < display_plugin.available_version:
                return (_('A new version of this plugin is available')+'\n\n'+
                                _('Right-click to see more options'))
        except Exception:
            return (_('A new version of this plugin is available')+'\n\n'+
                            _('Right-click to see more options'))
        return (_('This plugin is installed and up-to-date')+'\n\n'+
                        _('Right-click to see more options'))


class PluginUpdaterDialog(SizePersistedDialog):

    initial_extra_size = QSize(350, 100)
    forum_label_text = _('Plugin homepage')

    def __init__(self, gui, initial_filter=FILTER_UPDATE_AVAILABLE):
        SizePersistedDialog.__init__(self, gui, 'Plugin Updater plugin:plugin updater dialog')
        self.gui = gui
        self.forum_link = None
        self.zip_url = None
        self.model = None
        self.do_restart = False
        self._initialize_controls()
        self._create_context_menu()

        try:
            display_plugins = read_available_plugins(raise_error=True)
        except Exception:
            display_plugins = []
            import traceback
            error_dialog(self.gui, _('Update Check Failed'),
                        _('Unable to reach the plugin index page.'),
                        det_msg=traceback.format_exc(), show=True)

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
            self.filter_combo.setEnabled(False)
        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def _initialize_controls(self):
        self.setWindowTitle(_('User plugins'))
        self.setWindowIcon(QIcon.ic('plugins/plugin_updater.png'))
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        title_layout = ImageTitleLayout(self, 'plugins/plugin_updater.png',
                _('User plugins'))
        layout.addLayout(title_layout)

        header_layout = QHBoxLayout()
        layout.addLayout(header_layout)
        self.filter_combo = PluginFilterComboBox(self)
        self.filter_combo.setMinimumContentsLength(20)
        self.filter_combo.currentIndexChanged.connect(self._filter_combo_changed)
        la = QLabel(_('Filter list of &plugins')+':', self)
        la.setBuddy(self.filter_combo)
        header_layout.addWidget(la)
        header_layout.addWidget(self.filter_combo)
        header_layout.addStretch(10)

        # filter plugins by name
        la = QLabel(_('Filter by &name')+':', self)
        header_layout.addWidget(la)
        self.filter_by_name_lineedit = QLineEdit(self)
        la.setBuddy(self.filter_by_name_lineedit)
        self.filter_by_name_lineedit.setText("")
        self.filter_by_name_lineedit.textChanged.connect(self._filter_name_lineedit_changed)

        header_layout.addWidget(self.filter_by_name_lineedit)

        self.plugin_view = QTableView(self)
        self.plugin_view.horizontalHeader().setStretchLastSection(True)
        self.plugin_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plugin_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.plugin_view.setAlternatingRowColors(True)
        self.plugin_view.setSortingEnabled(True)
        self.plugin_view.setIconSize(QSize(28, 28))
        layout.addWidget(self.plugin_view)

        details_layout = QHBoxLayout()
        layout.addLayout(details_layout)
        forum_label = self.forum_label = QLabel('')
        forum_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        forum_label.linkActivated.connect(self._forum_label_activated)
        details_layout.addWidget(QLabel(_('Description')+':', self), 0, Qt.AlignmentFlag.AlignLeft)
        details_layout.addWidget(forum_label, 1, Qt.AlignmentFlag.AlignRight)

        self.description = QLabel(self)
        self.description.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self.description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description.setMinimumHeight(40)
        self.description.setWordWrap(True)
        layout.addWidget(self.description)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        self.finished.connect(self._finished)
        self.install_button = self.button_box.addButton(_('&Install'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.install_button.setToolTip(_('Install the selected plugin'))
        self.install_button.clicked.connect(self._install_clicked)
        self.install_button.setEnabled(False)
        self.configure_button = self.button_box.addButton(' '+_('&Customize plugin ')+' ', QDialogButtonBox.ButtonRole.ResetRole)
        self.configure_button.setToolTip(_('Customize the options for this plugin'))
        self.configure_button.clicked.connect(self._configure_clicked)
        self.configure_button.setEnabled(False)
        layout.addWidget(self.button_box)

    def update_forum_label(self):
        txt = ''
        if self.forum_link:
            txt = f'<a href="{self.forum_link}">{self.forum_label_text}</a>'
        self.forum_label.setText(txt)

    def _create_context_menu(self):
        self.plugin_view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.install_action = QAction(QIcon.ic('plugins/plugin_upgrade_ok.png'), _('&Install'), self)
        self.install_action.setToolTip(_('Install the selected plugin'))
        self.install_action.triggered.connect(self._install_clicked)
        self.install_action.setEnabled(False)
        self.plugin_view.addAction(self.install_action)
        self.forum_action = QAction(QIcon.ic('plugins/mobileread.png'), _('Plugin &forum thread'), self)
        self.forum_action.triggered.connect(self._forum_label_activated)
        self.forum_action.setEnabled(False)
        self.plugin_view.addAction(self.forum_action)

        sep1 = QAction(self)
        sep1.setSeparator(True)
        self.plugin_view.addAction(sep1)

        self.toggle_enabled_action = QAction(_('Enable/&disable plugin'), self)
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

        self.donate_enabled_action = QAction(QIcon.ic('donate.png'), _('Donate to developer'), self)
        self.donate_enabled_action.setToolTip(_('Donate to the developer of this plugin'))
        self.donate_enabled_action.triggered.connect(self._donate_clicked)
        self.donate_enabled_action.setEnabled(False)
        self.plugin_view.addAction(self.donate_enabled_action)

        sep3 = QAction(self)
        sep3.setSeparator(True)
        self.plugin_view.addAction(sep3)

        self.configure_action = QAction(QIcon.ic('config.png'), _('&Customize plugin'), self)
        self.configure_action.setToolTip(_('Customize the options for this plugin'))
        self.configure_action.triggered.connect(self._configure_clicked)
        self.configure_action.setEnabled(False)
        self.plugin_view.addAction(self.configure_action)

    def _finished(self, *args):
        if self.model:
            update_plugins = list(filter(filter_upgradeable_plugins, self.model.display_plugins))
            self.gui.recalc_update_label(len(update_plugins))

    def _plugin_current_changed(self, current, previous):
        if current.isValid():
            actual_idx = self.proxy_model.mapToSource(current)
            display_plugin = self.model.display_plugins[actual_idx.row()]
            self.description.setText(display_plugin.description)
            self.forum_link = display_plugin.forum_link
            self.zip_url = display_plugin.zip_url
            self.forum_action.setEnabled(bool(self.forum_link))
            self.install_button.setEnabled(display_plugin.is_valid_to_install())
            self.install_action.setEnabled(self.install_button.isEnabled())
            self.uninstall_action.setEnabled(display_plugin.is_installed())
            self.configure_button.setEnabled(display_plugin.is_installed())
            self.configure_action.setEnabled(self.configure_button.isEnabled())
            self.toggle_enabled_action.setEnabled(display_plugin.is_installed())
            self.donate_enabled_action.setEnabled(bool(display_plugin.donation_link))
        else:
            self.description.setText('')
            self.forum_link = None
            self.zip_url = None
            self.forum_action.setEnabled(False)
            self.install_button.setEnabled(False)
            self.install_action.setEnabled(False)
            self.uninstall_action.setEnabled(False)
            self.configure_button.setEnabled(False)
            self.configure_action.setEnabled(False)
            self.toggle_enabled_action.setEnabled(False)
            self.donate_enabled_action.setEnabled(False)
        self.update_forum_label()

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
        self.filter_by_name_lineedit.setText("")  # clear the name filter text when a different group was selected
        self.proxy_model.set_filter_criteria(idx)
        if idx == FILTER_NOT_INSTALLED:
            self.plugin_view.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        else:
            self.plugin_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._select_and_focus_view()

    def _filter_name_lineedit_changed(self, text):
        self.proxy_model.set_filter_text(text)  # set the filter text for filterAcceptsRow

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
            if display_plugin.qname == name_to_remove:
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
        self._uninstall_plugin(display_plugin.qname)
        if self.proxy_model.filter_criteria in [FILTER_INSTALLED, FILTER_UPDATE_AVAILABLE]:
            self.model.beginResetModel(), self.model.endResetModel()
            self._select_and_focus_view()
        else:
            self._select_and_focus_view(change_selection=False)

    def _install_clicked(self):
        display_plugin = self._selected_display_plugin()
        if not question_dialog(self, _('Install %s')%display_plugin.name, '<p>' +
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

        plugin_zip_url = display_plugin.zip_url
        if DEBUG:
            prints('Downloading plugin ZIP attachment: ', plugin_zip_url)
        self.gui.status_bar.showMessage(_('Downloading plugin ZIP attachment: %s') % plugin_zip_url)
        zip_path = self._download_zip(plugin_zip_url)

        if DEBUG:
            prints('Installing plugin: ', zip_path)
        self.gui.status_bar.showMessage(_('Installing plugin: %s') % zip_path)

        do_restart = False
        try:
            from calibre.customize.ui import config
            installed_plugins = frozenset(config['plugins'])
            try:
                plugin = add_plugin(zip_path)
            except NameConflict as e:
                return error_dialog(self.gui, _('Already exists'),
                        str(e), show=True)
            # Check for any toolbars to add to.
            widget = ConfigWidget(self.gui)
            widget.gui = self.gui
            widget.check_for_add_to_toolbars(plugin, previously_installed=plugin.name in installed_plugins)
            self.gui.status_bar.showMessage(_('Plugin installed: %s') % display_plugin.name)
            d = info_dialog(self.gui, _('Success'),
                    _('Plugin <b>{0}</b> successfully installed under <b>'
                        '{1}</b>. You may have to restart calibre '
                        'for the plugin to take effect.').format(plugin.name, plugin.type),
                    show_copy_button=False)
            b = d.bb.addButton(_('&Restart calibre now'), QDialogButtonBox.ButtonRole.AcceptRole)
            b.setIcon(QIcon.ic('lt.png'))
            d.do_restart = False

            def rf():
                d.do_restart = True
            b.clicked.connect(rf)
            d.set_details('')
            d.exec()
            b.clicked.disconnect()
            do_restart = d.do_restart

            display_plugin.plugin = plugin
            # We cannot read the 'actual' version information as the plugin will not be loaded yet
            display_plugin.installed_version = display_plugin.available_version
        except:
            if DEBUG:
                prints('ERROR occurred while installing plugin: %s'%display_plugin.name)
                traceback.print_exc()
            error_dialog(self.gui, _('Install plugin failed'),
                         _('A problem occurred while installing this plugin.'
                           ' This plugin will now be uninstalled.'
                           ' Please post the error message in details below into'
                           ' the forum thread for this plugin and restart calibre.'),
                         det_msg=traceback.format_exc(), show=True)
            if DEBUG:
                prints('Due to error now uninstalling plugin: %s'%display_plugin.name)
            remove_plugin(display_plugin.name)
            display_plugin.plugin = None

        display_plugin.uninstall_plugins = []
        if self.proxy_model.filter_criteria in [FILTER_NOT_INSTALLED, FILTER_UPDATE_AVAILABLE]:
            self.model.beginResetModel(), self.model.endResetModel()
            self._select_and_focus_view()
        else:
            self.model.refresh_plugin(display_plugin)
            self._select_and_focus_view(change_selection=False)
        if do_restart:
            self.do_restart = True
            self.accept()

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

    def _download_zip(self, plugin_zip_url):
        from calibre.ptempfile import PersistentTemporaryFile
        raw = get_https_resource_securely(plugin_zip_url, headers={'User-Agent':f'{__appname__} {__version__}'})
        with PersistentTemporaryFile('.zip') as pt:
            pt.write(raw)
        return pt.name
