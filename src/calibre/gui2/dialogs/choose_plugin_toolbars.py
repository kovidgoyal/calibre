#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'


from PyQt5.Qt import (QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
            QListWidget, QAbstractItemView, QSizePolicy)


class ChoosePluginToolbarsDialog(QDialog):

    def __init__(self, parent, plugin, locations):
        QDialog.__init__(self, parent)
        self.locations = locations

        self.setWindowTitle(
            _('Add "%s" to toolbars or menus')%plugin.name)

        self._layout = QVBoxLayout(self)
        self.setLayout(self._layout)

        self._header_label = QLabel(
                _('Select the toolbars and/or menus to add <b>%s</b> to:') %
                plugin.name)
        self._layout.addWidget(self._header_label)

        self._locations_list = QListWidget(self)
        self._locations_list.setSelectionMode(QAbstractItemView.MultiSelection)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self._locations_list.setSizePolicy(sizePolicy)
        for key, text in locations:
            self._locations_list.addItem(text)
            if key in {'toolbar', 'toolbar-device'}:
                self._locations_list.item(self._locations_list.count()-1
                        ).setSelected(True)
        self._layout.addWidget(self._locations_list)

        self._footer_label = QLabel(
            _('You can also customise the plugin locations '
              'using <b>Preferences -> Interface -> Toolbars</b>'))
        self._layout.addWidget(self._footer_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok |
                QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._layout.addWidget(button_box)
        self.resize(self.sizeHint())

    def selected_locations(self):
        selected = []
        for row in self._locations_list.selectionModel().selectedRows():
            selected.append(self.locations[row.row()])
        return selected
