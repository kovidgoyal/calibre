#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter
from qt.core import (
    QAbstractListModel, QAbstractTableModel, QDialogButtonBox, QFrame, QIcon, QLabel,
    QScrollArea, Qt, QVBoxLayout, QWidget, pyqtSignal, QDialog
)

from calibre.customize.ui import (
    all_metadata_plugins, default_disabled_plugins, disable_plugin, enable_plugin,
    is_disabled
)
from calibre.ebooks.metadata.sources.prefs import msprefs
from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.metadata_sources_ui import Ui_Form
from polyglot.builtins import iteritems


class SourcesModel(QAbstractTableModel):  # {{{

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.gui_parent = parent

        self.plugins = []
        self.enabled_overrides = {}
        self.cover_overrides = {}

    def initialize(self):
        self.beginResetModel()
        self.plugins = list(all_metadata_plugins())
        self.plugins.sort(key=attrgetter('name'))
        self.enabled_overrides = {}
        self.cover_overrides = {}
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.plugins)

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return _('Source')
            if section == 1:
                return _('Cover priority')
        return None

    def data(self, index, role):
        try:
            plugin = self.plugins[index.row()]
        except:
            return None
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 0:
                return plugin.name
            elif col == 1:
                orig = msprefs['cover_priorities'].get(plugin.name, 1)
                return self.cover_overrides.get(plugin, orig)
        elif role == Qt.ItemDataRole.CheckStateRole and col == 0:
            orig = Qt.CheckState.Unchecked if is_disabled(plugin) else Qt.CheckState.Checked
            return self.enabled_overrides.get(plugin, orig)
        elif role == Qt.ItemDataRole.UserRole:
            return plugin
        elif (role == Qt.ItemDataRole.DecorationRole and col == 0 and not
                    plugin.is_configured()):
            return QIcon.ic('list_remove.png')
        elif role == Qt.ItemDataRole.ToolTipRole:
            base = plugin.description + '\n\n'
            if plugin.is_configured():
                return base + _('This source is configured and ready to go')
            return base + _('This source needs configuration')
        return None

    def setData(self, index, val, role):
        try:
            plugin = self.plugins[index.row()]
        except:
            return False
        col = index.column()
        ret = False
        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            val = Qt.CheckState(val)
            if val == Qt.CheckState.Checked and 'Douban' in plugin.name:
                if not question_dialog(self.gui_parent,
                    _('Are you sure?'), '<p>'+
                    _('This plugin is useful only for <b>Chinese</b>'
                        ' language books. It can return incorrect'
                        ' results for books in English. Are you'
                        ' sure you want to enable it?'),
                    show_copy_button=False):
                    return ret
            self.enabled_overrides[plugin] = val
            ret = True
        if col == 1 and role == Qt.ItemDataRole.EditRole:
            try:
                self.cover_overrides[plugin] = max(1, int(val))
                ret = True
            except (ValueError, TypeError):
                pass
        if ret:
            self.dataChanged.emit(index, index)
        return ret

    def flags(self, index):
        col = index.column()
        ans = QAbstractTableModel.flags(self, index)
        if col == 0:
            return ans | Qt.ItemFlag.ItemIsUserCheckable
        return Qt.ItemFlag.ItemIsEditable | ans

    def commit(self):
        for plugin, val in iteritems(self.enabled_overrides):
            if val == Qt.CheckState.Checked:
                enable_plugin(plugin)
            elif val == Qt.CheckState.Unchecked:
                disable_plugin(plugin)

        if self.cover_overrides:
            cp = msprefs['cover_priorities']
            for plugin, val in iteritems(self.cover_overrides):
                if val == 1:
                    cp.pop(plugin.name, None)
                else:
                    cp[plugin.name] = val
            msprefs['cover_priorities'] = cp

        self.enabled_overrides = {}
        self.cover_overrides = {}

    def restore_defaults(self):
        self.beginResetModel()
        self.enabled_overrides = {p: (Qt.CheckState.Unchecked if p.name in
            default_disabled_plugins else Qt.CheckState.Checked) for p in self.plugins}
        self.cover_overrides = {p:
            msprefs.defaults['cover_priorities'].get(p.name, 1)
                for p in self.plugins}
        self.endResetModel()

# }}}


class FieldsModel(QAbstractListModel):  # {{{

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)

        self.fields = []
        self.descs = {
                'authors': _('Authors'),
                'comments': _('Comments'),
                'pubdate': _('Published date'),
                'publisher': _('Publisher'),
                'rating' : _('Rating'),
                'tags' : _('Tags'),
                'title': _('Title'),
                'series': ngettext('Series', 'Series', 1),
                'languages': _('Languages'),
        }
        self.overrides = {}
        self.exclude = frozenset([
            'series_index', 'language'  # some plugins use language instead of languages
        ])

    def rowCount(self, parent=None):
        return len(self.fields)

    def initialize(self):
        fields = set()
        for p in all_metadata_plugins():
            fields |= p.touched_fields
        self.beginResetModel()
        self.fields = []
        for x in fields:
            if not x.startswith('identifier:') and x not in self.exclude:
                self.fields.append(x)
        self.fields.sort(key=lambda x:self.descs.get(x, x))
        self.endResetModel()

    def state(self, field, defaults=False):
        src = msprefs.defaults if defaults else msprefs
        return (Qt.CheckState.Unchecked if field in src['ignore_fields']
                    else Qt.CheckState.Checked)

    def data(self, index, role):
        try:
            field = self.fields[index.row()]
        except:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.descs.get(field, field)
        if role == Qt.ItemDataRole.CheckStateRole:
            return self.overrides.get(field, self.state(field))
        return None

    def flags(self, index):
        ans = QAbstractListModel.flags(self, index)
        return ans | Qt.ItemFlag.ItemIsUserCheckable

    def restore_defaults(self):
        self.beginResetModel()
        self.overrides = {f: self.state(f, True) for f in self.fields}
        self.endResetModel()

    def select_all(self):
        self.beginResetModel()
        self.overrides = {f: Qt.CheckState.Checked for f in self.fields}
        self.endResetModel()

    def clear_all(self):
        self.beginResetModel()
        self.overrides = {f: Qt.CheckState.Unchecked for f in self.fields}
        self.endResetModel()

    def setData(self, index, val, role):
        try:
            field = self.fields[index.row()]
        except:
            return False
        ret = False
        if role == Qt.ItemDataRole.CheckStateRole:
            self.overrides[field] = Qt.CheckState(val)
            ret = True
        if ret:
            self.dataChanged.emit(index, index)
        return ret

    def commit(self):
        ignored_fields = {x for x in msprefs['ignore_fields'] if x not in
            self.overrides}
        changed = {k for k, v in iteritems(self.overrides) if v ==
            Qt.CheckState.Unchecked}
        msprefs['ignore_fields'] = list(ignored_fields.union(changed))

    def user_default_state(self, field):
        return (Qt.CheckState.Unchecked if field in msprefs.get('user_default_ignore_fields',[])
                    else Qt.CheckState.Checked)

    def select_user_defaults(self):
        self.beginResetModel()
        self.overrides = {f: self.user_default_state(f) for f in self.fields}
        self.endResetModel()

    def commit_user_defaults(self):
        default_ignored_fields = {x for x in msprefs['user_default_ignore_fields'] if x not in
            self.overrides}
        changed = {k for k, v in iteritems(self.overrides) if v ==
            Qt.CheckState.Unchecked}
        msprefs['user_default_ignore_fields'] = list(default_ignored_fields.union(changed))

# }}}


class PluginConfig(QWidget):  # {{{

    finished = pyqtSignal()

    def __init__(self, plugin, parent):
        QWidget.__init__(self, parent)

        self.plugin = plugin

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.c = c = QLabel(_('<b>Configure %(name)s</b><br>%(desc)s') % dict(
            name=plugin.name, desc=plugin.description))
        c.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(c)

        self.config_widget = plugin.config_widget()
        self.sa = sa = QScrollArea(self)
        sa.setWidgetResizable(True)
        sa.setWidget(self.config_widget)
        l.addWidget(sa)

        self.bb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,
                parent=self)
        self.bb.accepted.connect(self.finished)
        self.bb.rejected.connect(self.finished)
        self.bb.accepted.connect(self.commit)
        l.addWidget(self.bb)

        self.f = QFrame(self)
        self.f.setFrameShape(QFrame.Shape.HLine)
        l.addWidget(self.f)

    def commit(self):
        self.plugin.save_settings(self.config_widget)
# }}}


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        r = self.register
        r('txt_comments', msprefs)
        r('max_tags', msprefs)
        r('wait_after_first_identify_result', msprefs)
        r('wait_after_first_cover_result', msprefs)
        r('swap_author_names', msprefs)
        r('fewer_tags', msprefs)
        r('keep_dups', msprefs)
        r('append_comments', msprefs)

        self.configure_plugin_button.clicked.connect(self.configure_plugin)
        self.sources_model = SourcesModel(self)
        self.sources_view.setModel(self.sources_model)
        self.sources_model.dataChanged.connect(self.changed_signal)

        self.fields_model = FieldsModel(self)
        self.fields_view.setModel(self.fields_model)
        self.fields_model.dataChanged.connect(self.changed_signal)

        self.select_all_button.clicked.connect(self.fields_model.select_all)
        self.select_all_button.clicked.connect(self.changed_signal)
        self.clear_all_button.clicked.connect(self.fields_model.clear_all)
        self.clear_all_button.clicked.connect(self.changed_signal)
        self.select_default_button.clicked.connect(self.fields_model.select_user_defaults)
        self.select_default_button.clicked.connect(self.changed_signal)
        self.set_as_default_button.clicked.connect(self.fields_model.commit_user_defaults)
        self.tag_map_rules = self.author_map_rules = None
        self.tag_map_rules_button.clicked.connect(self.change_tag_map_rules)
        self.author_map_rules_button.clicked.connect(self.change_author_map_rules)
        l = self.page.layout()
        l.setStretch(0, 1)
        l.setStretch(1, 1)

    def configure_plugin(self):
        for index in self.sources_view.selectionModel().selectedRows():
            plugin = self.sources_model.data(index, Qt.ItemDataRole.UserRole)
            if plugin is not None:
                return self.do_config(plugin)
        error_dialog(self, _('No source selected'),
                _('No source selected, cannot configure.'), show=True)

    def do_config(self, plugin):
        self.pc = PluginConfig(plugin, self)
        self.stack.insertWidget(1, self.pc)
        self.stack.setCurrentIndex(1)
        self.pc.finished.connect(self.pc_finished)

    def pc_finished(self):
        try:
            self.pc.finished.diconnect()
        except:
            pass
        self.stack.setCurrentIndex(0)
        self.stack.removeWidget(self.pc)
        self.pc = None

    def change_tag_map_rules(self):
        from calibre.gui2.tag_mapper import RulesDialog
        d = RulesDialog(self)
        if msprefs.get('tag_map_rules'):
            d.rules = msprefs['tag_map_rules']
        if d.exec() == QDialog.DialogCode.Accepted:
            self.tag_map_rules = d.rules
            self.changed_signal.emit()

    def change_author_map_rules(self):
        from calibre.gui2.author_mapper import RulesDialog
        d = RulesDialog(self)
        if msprefs.get('author_map_rules'):
            d.rules = msprefs['author_map_rules']
        if d.exec() == QDialog.DialogCode.Accepted:
            self.author_map_rules = d.rules
            self.changed_signal.emit()

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.sources_model.initialize()
        self.sources_view.resizeColumnsToContents()
        self.fields_model.initialize()
        self.tag_map_rules = self.author_map_rules = None

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.sources_model.restore_defaults()
        self.fields_model.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        self.sources_model.commit()
        self.fields_model.commit()
        if self.tag_map_rules is not None:
            msprefs['tag_map_rules'] = self.tag_map_rules or []
        if self.author_map_rules is not None:
            msprefs['author_map_rules'] = self.author_map_rules or []
        return ConfigWidgetBase.commit(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Sharing', 'Metadata download')
