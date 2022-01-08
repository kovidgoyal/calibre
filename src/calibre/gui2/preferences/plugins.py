#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os
from collections import OrderedDict

from qt.core import (Qt, QMenu, QModelIndex, QAbstractItemModel, QIcon,
        QBrush, QDialog, QItemSelectionModel, QAbstractItemView)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.plugins_ui import Ui_Form
from calibre.customize import PluginInstallationType
from calibre.customize.ui import (initialized_plugins, is_disabled, enable_plugin,
                                 disable_plugin, plugin_customization, add_plugin,
                                 remove_plugin, NameConflict)
from calibre.gui2 import (error_dialog, info_dialog, choose_files,
        question_dialog, gprefs)
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.icu import lower
from calibre.constants import iswindows
from polyglot.builtins import iteritems, itervalues


class AdaptSQP(SearchQueryParser):

    def __init__(self, *args, **kwargs):
        pass


class PluginModel(QAbstractItemModel, AdaptSQP):  # {{{

    def __init__(self, show_only_user_plugins=False):
        QAbstractItemModel.__init__(self)
        SearchQueryParser.__init__(self, ['all'])
        self.show_only_user_plugins = show_only_user_plugins
        self.icon = QIcon.ic('plugins.png')
        p = self.icon.pixmap(64, 64, QIcon.Mode.Disabled, QIcon.State.On)
        self.disabled_icon = QIcon(p)
        self._p = p
        self.populate()

    def toggle_shown_plugins(self, show_only_user_plugins):
        self.show_only_user_plugins = show_only_user_plugins
        self.beginResetModel()
        self.populate()
        self.endResetModel()

    def populate(self):
        self._data = {}
        for plugin in initialized_plugins():
            if (getattr(plugin, 'installation_type', None) is not PluginInstallationType.EXTERNAL and self.show_only_user_plugins):
                continue
            if plugin.type not in self._data:
                self._data[plugin.type] = [plugin]
            else:
                self._data[plugin.type].append(plugin)
        self.categories = sorted(self._data.keys())

        for plugins in self._data.values():
            plugins.sort(key=lambda x: x.name.lower())

    def universal_set(self):
        ans = set()
        for c, category in enumerate(self.categories):
            ans.add((c, -1))
            for p, plugin in enumerate(self._data[category]):
                ans.add((c, p))
        return ans

    def get_matches(self, location, query, candidates=None):
        if candidates is None:
            candidates = self.universal_set()
        ans = set()
        if not query:
            return ans
        query = lower(query)
        for c, p in candidates:
            if p < 0:
                if query in lower(self.categories[c]):
                    ans.add((c, p))
                continue
            else:
                try:
                    plugin = self._data[self.categories[c]][p]
                except:
                    continue
            if query in lower(plugin.name) or query in lower(plugin.author) or \
                    query in lower(plugin.description):
                ans.add((c, p))
        return ans

    def find(self, query):
        query = query.strip()
        if not query:
            return QModelIndex()
        matches = self.parse(query)
        if not matches:
            return QModelIndex()
        matches = list(sorted(matches))
        c, p = matches[0]
        cat_idx = self.index(c, 0, QModelIndex())
        if p == -1:
            return cat_idx
        return self.index(p, 0, cat_idx)

    def find_next(self, idx, query, backwards=False):
        query = query.strip()
        if not query:
            return idx
        matches = self.parse(query)
        if not matches:
            return idx
        if idx.parent().isValid():
            loc = (idx.parent().row(), idx.row())
        else:
            loc = (idx.row(), -1)
        if loc not in matches:
            return self.find(query)
        if len(matches) == 1:
            return QModelIndex()
        matches = list(sorted(matches))
        i = matches.index(loc)
        if backwards:
            ans = i - 1 if i - 1 >= 0 else len(matches)-1
        else:
            ans = i + 1 if i + 1 < len(matches) else 0

        ans = matches[ans]

        return self.index(ans[0], 0, QModelIndex()) if ans[1] < 0 else \
                self.index(ans[1], 0, self.index(ans[0], 0, QModelIndex()))

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if parent.isValid():
            return self.createIndex(row, column, 1+parent.row())
        else:
            return self.createIndex(row, column, 0)

    def parent(self, index):
        if not index.isValid() or index.internalId() == 0:
            return QModelIndex()
        return self.createIndex(index.internalId()-1, 0, 0)

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.categories)
        if parent.internalId() == 0:
            category = self.categories[parent.row()]
            return len(self._data[category])
        return 0

    def columnCount(self, parent):
        return 1

    def index_to_plugin(self, index):
        category = self.categories[index.parent().row()]
        return self._data[category][index.row()]

    def plugin_to_index(self, plugin):
        for i, category in enumerate(self.categories):
            parent = self.index(i, 0, QModelIndex())
            for j, p in enumerate(self._data[category]):
                if plugin == p:
                    return self.index(j, 0, parent)
        return QModelIndex()

    def plugin_to_index_by_properties(self, plugin):
        for i, category in enumerate(self.categories):
            parent = self.index(i, 0, QModelIndex())
            for j, p in enumerate(self._data[category]):
                if plugin.name == p.name and plugin.type == p.type and \
                        plugin.author == p.author and plugin.version == p.version:
                    return self.index(j, 0, parent)
        return QModelIndex()

    def refresh_plugin(self, plugin, rescan=False):
        if rescan:
            self.populate()
        idx = self.plugin_to_index(plugin)
        self.dataChanged.emit(idx, idx)

    def flags(self, index):
        if not index.isValid():
            return 0
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        return flags

    def data(self, index, role):
        if not index.isValid():
            return None
        if index.internalId() == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.categories[index.row()]
        else:
            plugin = self.index_to_plugin(index)
            disabled = is_disabled(plugin)
            if role == Qt.ItemDataRole.DisplayRole:
                ver = '.'.join(map(str, plugin.version))
                desc = '\n'.join(textwrap.wrap(plugin.description, 100))
                ans='%s (%s) %s %s\n%s'%(plugin.name, ver, _('by'), plugin.author, desc)
                c = plugin_customization(plugin)
                if c and not disabled:
                    ans += _('\nCustomization: ')+c
                if disabled:
                    ans += _('\n\nThis plugin has been disabled')
                if plugin.installation_type is PluginInstallationType.SYSTEM:
                    ans += _('\n\nThis plugin is installed system-wide and can not be managed from within calibre')
                return (ans)
            if role == Qt.ItemDataRole.DecorationRole:
                return self.disabled_icon if disabled else self.icon
            if role == Qt.ItemDataRole.ForegroundRole and disabled:
                return (QBrush(Qt.GlobalColor.gray))
            if role == Qt.ItemDataRole.UserRole:
                return plugin
        return None


# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    supports_restoring_to_defaults = False

    def genesis(self, gui):
        self.gui = gui
        self._plugin_model = PluginModel(self.user_installed_plugins.isChecked())
        self.plugin_view.setModel(self._plugin_model)
        self.plugin_view.setStyleSheet(
                "QTreeView::item { padding-bottom: 10px;}")
        self.plugin_view.doubleClicked.connect(self.double_clicked)
        self.toggle_plugin_button.clicked.connect(self.toggle_plugin)
        self.customize_plugin_button.clicked.connect(self.customize_plugin)
        self.remove_plugin_button.clicked.connect(self.remove_plugin)
        self.button_plugin_add.clicked.connect(self.add_plugin)
        self.button_plugin_updates.clicked.connect(self.update_plugins)
        self.button_plugin_new.clicked.connect(self.get_plugins)
        self.search.initialize('plugin_search_history',
                help_text=_('Search for plugin'))
        self.search.search.connect(self.find)
        self.next_button.clicked.connect(self.find_next)
        self.previous_button.clicked.connect(self.find_previous)
        self.changed_signal.connect(self.reload_store_plugins)
        self.user_installed_plugins.stateChanged.connect(self.show_user_installed_plugins)
        self.plugin_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.plugin_view.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(QIcon.ic('plus.png'), _('Expand all'), self.plugin_view.expandAll)
        menu.addAction(QIcon.ic('minus.png'), _('Collapse all'), self.plugin_view.collapseAll)
        menu.exec(self.plugin_view.mapToGlobal(pos))

    def show_user_installed_plugins(self, state):
        self._plugin_model.toggle_shown_plugins(self.user_installed_plugins.isChecked())

    def find(self, query):
        idx = self._plugin_model.find(query)
        if not idx.isValid():
            return info_dialog(self, _('No matches'),
                    _('Could not find any matching plugins'), show=True,
                    show_copy_button=False)
        self.highlight_index(idx)

    def highlight_index(self, idx):
        self.plugin_view.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self.plugin_view.setCurrentIndex(idx)
        self.plugin_view.setFocus(Qt.FocusReason.OtherFocusReason)
        self.plugin_view.scrollTo(idx, QAbstractItemView.ScrollHint.EnsureVisible)

    def find_next(self, *args):
        idx = self.plugin_view.currentIndex()
        if not idx.isValid():
            idx = self._plugin_model.index(0, 0)
        idx = self._plugin_model.find_next(idx,
                str(self.search.currentText()))
        self.highlight_index(idx)

    def find_previous(self, *args):
        idx = self.plugin_view.currentIndex()
        if not idx.isValid():
            idx = self._plugin_model.index(0, 0)
        idx = self._plugin_model.find_next(idx,
            str(self.search.currentText()), backwards=True)
        self.highlight_index(idx)

    def toggle_plugin(self, *args):
        self.modify_plugin(op='toggle')

    def double_clicked(self, index):
        if index.parent().isValid():
            self.modify_plugin(op='customize')

    def customize_plugin(self, *args):
        self.modify_plugin(op='customize')

    def remove_plugin(self, *args):
        self.modify_plugin(op='remove')

    def add_plugin(self):
        info = '' if iswindows else ' [.zip %s]'%_('files')
        path = choose_files(self, 'add a plugin dialog', _('Add plugin'),
                filters=[(_('Plugins') + info, ['zip'])], all_files=False,
                    select_only_single_file=True)
        if not path:
            return
        path = path[0]
        if path and os.access(path, os.R_OK) and path.lower().endswith('.zip'):
            if not question_dialog(self, _('Are you sure?'), '<p>' +
                    _('Installing plugins is a <b>security risk</b>. '
                    'Plugins can contain a virus/malware. '
                        'Only install it if you got it from a trusted source.'
                        ' Are you sure you want to proceed?'),
                    show_copy_button=False):
                return
            from calibre.customize.ui import config
            installed_plugins = frozenset(config['plugins'])
            try:
                plugin = add_plugin(path)
            except NameConflict as e:
                return error_dialog(self, _('Already exists'),
                        str(e), show=True)
            self._plugin_model.beginResetModel()
            self._plugin_model.populate()
            self._plugin_model.endResetModel()
            self.changed_signal.emit()
            self.check_for_add_to_toolbars(plugin, previously_installed=plugin.name in installed_plugins)
            info_dialog(self, _('Success'),
                    _('Plugin <b>{0}</b> successfully installed under <b>'
                        '{1}</b>. You may have to restart calibre '
                        'for the plugin to take effect.').format(plugin.name, plugin.type),
                    show=True, show_copy_button=False)
            idx = self._plugin_model.plugin_to_index_by_properties(plugin)
            if idx.isValid():
                self.highlight_index(idx)
        else:
            error_dialog(self, _('No valid plugin path'),
                         _('%s is not a valid plugin path')%path).exec()

    def modify_plugin(self, op=''):
        index = self.plugin_view.currentIndex()
        if index.isValid():
            if not index.parent().isValid():
                name = str(index.data() or '')
                return error_dialog(self, _('Error'), '<p>'+
                        _('Select an actual plugin under <b>%s</b> to customize')%name,
                        show=True, show_copy_button=False)

            plugin = self._plugin_model.index_to_plugin(index)
            if op == 'toggle':
                if not plugin.can_be_disabled:
                    info_dialog(self, _('Plugin cannot be disabled'),
                                 _('Disabling the plugin %s is not allowed')%plugin.name, show=True, show_copy_button=False)
                    return
                if is_disabled(plugin):
                    enable_plugin(plugin)
                else:
                    disable_plugin(plugin)
                self._plugin_model.refresh_plugin(plugin)
                self.changed_signal.emit()
            if op == 'customize':
                if not plugin.is_customizable():
                    info_dialog(self, _('Plugin not customizable'),
                        _('Plugin: %s does not need customization')%plugin.name).exec()
                    return
                self.changed_signal.emit()
                from calibre.customize import InterfaceActionBase
                if isinstance(plugin, InterfaceActionBase) and not getattr(plugin,
                        'actual_iaction_plugin_loaded', False):
                    return error_dialog(self, _('Must restart'),
                            _('You must restart calibre before you can'
                                ' configure the <b>%s</b> plugin')%plugin.name, show=True)
                if plugin.do_user_config(self.gui):
                    self._plugin_model.refresh_plugin(plugin)
            elif op == 'remove':
                if not confirm('<p>' +
                    _('Are you sure you want to remove the plugin: %s?')%
                    f'<b>{plugin.name}</b>',
                    'confirm_plugin_removal_msg', parent=self):
                    return

                msg = _('Plugin <b>{0}</b> successfully removed. You will have'
                        ' to restart calibre for it to be completely removed.').format(plugin.name)
                if remove_plugin(plugin):
                    self._plugin_model.beginResetModel()
                    self._plugin_model.populate()
                    self._plugin_model.endResetModel()
                    self.changed_signal.emit()
                    info_dialog(self, _('Success'), msg, show=True,
                            show_copy_button=False)
                else:
                    error_dialog(self, _('Cannot remove builtin plugin'),
                         plugin.name + _(' cannot be removed. It is a '
                         'builtin plugin. Try disabling it instead.')).exec()

    def get_plugins(self):
        self.update_plugins(not_installed=True)

    def update_plugins(self, not_installed=False):
        from calibre.gui2.dialogs.plugin_updater import (PluginUpdaterDialog,
                                FILTER_UPDATE_AVAILABLE, FILTER_NOT_INSTALLED)
        mode = FILTER_NOT_INSTALLED if not_installed else FILTER_UPDATE_AVAILABLE
        d = PluginUpdaterDialog(self.gui, initial_filter=mode)
        d.exec()
        self._plugin_model.beginResetModel()
        self._plugin_model.populate()
        self._plugin_model.endResetModel()
        self.changed_signal.emit()
        if d.do_restart:
            self.restart_now.emit()

    def reload_store_plugins(self):
        self.gui.load_store_plugins()
        if 'Store' in self.gui.iactions:
            self.gui.iactions['Store'].load_menu()

    def check_for_add_to_toolbars(self, plugin, previously_installed=True):
        from calibre.gui2.preferences.toolbar import ConfigWidget
        from calibre.customize import InterfaceActionBase, EditBookToolPlugin

        if isinstance(plugin, EditBookToolPlugin):
            return self.check_for_add_to_editor_toolbar(plugin, previously_installed)

        if not isinstance(plugin, InterfaceActionBase):
            return

        all_locations = OrderedDict(ConfigWidget.LOCATIONS)
        try:
            plugin_action = plugin.load_actual_plugin(self.gui)
        except:
            # Broken plugin, fails to initialize. Given that, it's probably
            # already configured, so we can just quit.
            return
        installed_actions = OrderedDict([
            (key, list(gprefs.get('action-layout-'+key, [])))
            for key in all_locations])

        # If this is an update, do nothing
        if previously_installed:
            return
        # If already installed in a GUI container, do nothing
        for action_names in itervalues(installed_actions):
            if plugin_action.name in action_names:
                return

        allowed_locations = [(key, text) for key, text in
                iteritems(all_locations) if key
                not in plugin_action.dont_add_to]
        if not allowed_locations:
            return  # This plugin doesn't want to live in the GUI

        from calibre.gui2.dialogs.choose_plugin_toolbars import ChoosePluginToolbarsDialog
        d = ChoosePluginToolbarsDialog(self, plugin_action, allowed_locations)
        if d.exec() == QDialog.DialogCode.Accepted:
            for key, text in d.selected_locations():
                installed_actions = list(gprefs.get('action-layout-'+key, []))
                installed_actions.append(plugin_action.name)
                gprefs['action-layout-'+key] = tuple(installed_actions)

    def check_for_add_to_editor_toolbar(self, plugin, previously_installed):
        if not previously_installed:
            from calibre.utils.config import JSONConfig
            prefs = JSONConfig('newly-installed-editor-plugins')
            pl = set(prefs.get('newly_installed_plugins', ()))
            pl.add(plugin.name)
            prefs['newly_installed_plugins'] = sorted(pl)


if __name__ == '__main__':
    from qt.core import QApplication
    app = QApplication([])
    test_widget('Advanced', 'Plugins')
