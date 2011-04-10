#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt4.Qt import (QAbstractTableModel, Qt)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.metadata_sources_ui import Ui_Form
from calibre.ebooks.metadata.sources.base import msprefs
from calibre.customize.ui import (all_metadata_plugins, is_disabled,
        enable_plugin, disable_plugin, restore_plugin_state_to_default)
from calibre.gui2 import NONE

class SourcesModel(QAbstractTableModel): # {{{

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)

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
        del msprefs['cover_priorities']
        self.enabled_overrides = {}
        self.cover_overrides = {}
        for plugin in self.plugins:
            restore_plugin_state_to_default(plugin)
        self.reset()

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        r = self.register
        r('txt_comments', msprefs)
        r('max_tags', msprefs)
        r('wait_after_first_identify_result', msprefs)
        r('wait_after_first_cover_result', msprefs)

        self.configure_plugin_button.clicked.connect(self.configure_plugin)
        self.sources_model = SourcesModel(self)
        self.sources_view.setModel(self.sources_model)
        self.sources_model.dataChanged.connect(self.changed_signal)

    def configure_plugin(self):
        pass

    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.sources_model.initialize()
        self.sources_view.resizeColumnsToContents()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.sources_model.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        self.sources_model.commit()
        return ConfigWidgetBase.commit(self)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    test_widget('Sharing', 'Metadata download')

