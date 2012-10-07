#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt4.Qt import (QAbstractTableModel, Qt, QAbstractListModel, QWidget,
        pyqtSignal, QVBoxLayout, QDialogButtonBox, QFrame, QLabel, QIcon)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.metadata_sources_ui import Ui_Form
from calibre.ebooks.metadata.sources.base import msprefs
from calibre.customize.ui import (all_metadata_plugins, is_disabled,
        enable_plugin, disable_plugin, default_disabled_plugins)
from calibre.gui2 import NONE, error_dialog, question_dialog

class SourcesModel(QAbstractTableModel): # {{{

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.gui_parent = parent

        self.plugins = []
        self.enabled_overrides = {}
        self.cover_overrides = {}

    def initialize(self):
        self.plugins = list(all_metadata_plugins())
        self.plugins.sort(key=attrgetter('name'))
        self.enabled_overrides = {}
        self.cover_overrides = {}
        self.reset()

    def rowCount(self, parent=None):
        return len(self.plugins)

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return _('Source')
            if section == 1:
                return _('Cover priority')
        return NONE

    def data(self, index, role):
        try:
            plugin = self.plugins[index.row()]
        except:
            return NONE
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return plugin.name
            elif col == 1:
                orig = msprefs['cover_priorities'].get(plugin.name, 1)
                return self.cover_overrides.get(plugin, orig)
        elif role == Qt.CheckStateRole and col == 0:
            orig = Qt.Unchecked if is_disabled(plugin) else Qt.Checked
            return self.enabled_overrides.get(plugin, orig)
        elif role == Qt.UserRole:
            return plugin
        elif (role == Qt.DecorationRole and col == 0 and not
                    plugin.is_configured()):
            return QIcon(I('list_remove.png'))
        elif role == Qt.ToolTipRole:
            base = plugin.description + '\n\n'
            if plugin.is_configured():
                return base + _('This source is configured and ready to go')
            return base + _('This source needs configuration')
        return NONE

    def setData(self, index, val, role):
        try:
            plugin = self.plugins[index.row()]
        except:
            return False
        col = index.column()
        ret = False
        if col == 0 and role == Qt.CheckStateRole:
            val, ok = val.toInt()
            if ok:
                if val == Qt.Checked and 'Douban' in plugin.name:
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
        if col == 1 and role == Qt.EditRole:
            val, ok = val.toInt()
            if ok:
                self.cover_overrides[plugin] = val
                ret = True
        if ret:
            self.dataChanged.emit(index, index)
        return ret


    def flags(self, index):
        col = index.column()
        ans = QAbstractTableModel.flags(self, index)
        if col == 0:
            return ans | Qt.ItemIsUserCheckable
        return Qt.ItemIsEditable | ans

    def commit(self):
        for plugin, val in self.enabled_overrides.iteritems():
            if val == Qt.Checked:
                enable_plugin(plugin)
            elif val == Qt.Unchecked:
                disable_plugin(plugin)

        if self.cover_overrides:
            cp = msprefs['cover_priorities']
            for plugin, val in self.cover_overrides.iteritems():
                if val == 1:
                    cp.pop(plugin.name, None)
                else:
                    cp[plugin.name] = val
            msprefs['cover_priorities'] = cp

        self.enabled_overrides = {}
        self.cover_overrides = {}

    def restore_defaults(self):
        self.enabled_overrides = dict([(p, (Qt.Unchecked if p.name in
            default_disabled_plugins else Qt.Checked)) for p in self.plugins])
        self.cover_overrides = dict([(p,
            msprefs.defaults['cover_priorities'].get(p.name, 1))
                for p in self.plugins])
        self.reset()

# }}}

class FieldsModel(QAbstractListModel): # {{{


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
                'series': _('Series'),
                'languages': _('Languages'),
        }
        self.overrides = {}
        self.exclude = frozenset(['series_index'])

    def rowCount(self, parent=None):
        return len(self.fields)

    def initialize(self):
        fields = set()
        for p in all_metadata_plugins():
            fields |= p.touched_fields
        self.fields = []
        for x in fields:
            if not x.startswith('identifier:') and x not in self.exclude:
                self.fields.append(x)
        self.fields.sort(key=lambda x:self.descs.get(x, x))
        self.reset()

    def state(self, field, defaults=False):
        src = msprefs.defaults if defaults else msprefs
        return (Qt.Unchecked if field in src['ignore_fields']
                    else Qt.Checked)

    def data(self, index, role):
        try:
            field = self.fields[index.row()]
        except:
            return None
        if role == Qt.DisplayRole:
            return self.descs.get(field, field)
        if role == Qt.CheckStateRole:
            return self.overrides.get(field, self.state(field))
        return NONE

    def flags(self, index):
        ans = QAbstractTableModel.flags(self, index)
        return ans | Qt.ItemIsUserCheckable

    def restore_defaults(self):
        self.overrides = dict([(f, self.state(f, Qt.Checked)) for f in self.fields])
        self.reset()

    def select_all(self):
        self.overrides = dict([(f, Qt.Checked) for f in self.fields])
        self.reset()

    def clear_all(self):
        self.overrides = dict([(f, Qt.Unchecked) for f in self.fields])
        self.reset()

    def setData(self, index, val, role):
        try:
            field = self.fields[index.row()]
        except:
            return False
        ret = False
        if role == Qt.CheckStateRole:
            val, ok = val.toInt()
            if ok:
                self.overrides[field] = val
                ret = True
        if ret:
            self.dataChanged.emit(index, index)
        return ret

    def commit(self):
        ignored_fields = set([x for x in msprefs['ignore_fields'] if x not in
            self.overrides])
        changed = set([k for k, v in self.overrides.iteritems() if v ==
            Qt.Unchecked])
        msprefs['ignore_fields'] = list(ignored_fields.union(changed))

    def user_default_state(self, field):
        return (Qt.Unchecked if field in msprefs.get('user_default_ignore_fields',[])
                    else Qt.Checked)

    def select_user_defaults(self):
        self.overrides = dict([(f, self.user_default_state(f)) for f in self.fields])
        self.reset()

    def commit_user_defaults(self):
        default_ignored_fields = set([x for x in msprefs['user_default_ignore_fields'] if x not in
            self.overrides])
        changed = set([k for k, v in self.overrides.iteritems() if v ==
            Qt.Unchecked])
        msprefs['user_default_ignore_fields'] = list(default_ignored_fields.union(changed))

# }}}

class PluginConfig(QWidget): # {{{

    finished = pyqtSignal()

    def __init__(self, plugin, parent):
        QWidget.__init__(self, parent)

        self.plugin = plugin

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.c = c = QLabel(_('<b>Configure %(name)s</b><br>%(desc)s') % dict(
            name=plugin.name, desc=plugin.description))
        c.setAlignment(Qt.AlignHCenter)
        l.addWidget(c)

        self.config_widget = plugin.config_widget()
        self.l.addWidget(self.config_widget)

        self.bb = QDialogButtonBox(
                QDialogButtonBox.Save|QDialogButtonBox.Cancel,
                parent=self)
        self.bb.accepted.connect(self.finished)
        self.bb.rejected.connect(self.finished)
        self.bb.accepted.connect(self.commit)
        l.addWidget(self.bb)

        self.f = QFrame(self)
        self.f.setFrameShape(QFrame.HLine)
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
        r('find_first_edition_date', msprefs)

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

    def configure_plugin(self):
        for index in self.sources_view.selectionModel().selectedRows():
            plugin = self.sources_model.data(index, Qt.UserRole)
            if plugin is not NONE:
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

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.sources_model.initialize()
        self.sources_view.resizeColumnsToContents()
        self.fields_model.initialize()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.sources_model.restore_defaults()
        self.fields_model.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        self.sources_model.commit()
        self.fields_model.commit()
        return ConfigWidgetBase.commit(self)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Sharing', 'Metadata download')

