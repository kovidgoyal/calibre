#!/usr/bin/env python


__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'


from qt.core import QAbstractItemView, QDialog, QDialogButtonBox, QLabel, QListWidget, QSizePolicy, QVBoxLayout

from calibre.utils.localization import _


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
        self._locations_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        self._locations_list.setSizePolicy(sizePolicy)
        for key, text in locations:
            self._locations_list.addItem(text)
            if key in {'toolbar', 'toolbar-device'}:
                _loc_item = self._locations_list.item(self._locations_list.count()-1)
                assert _loc_item is not None
                _loc_item.setSelected(True)
        self._layout.addWidget(self._locations_list)

        self._footer_label = QLabel(
            _('You can also customise the plugin locations '
              'using <b>Preferences -> Interface -> Toolbars</b>'))
        self._layout.addWidget(self._footer_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._layout.addWidget(button_box)
        self.resize(self.sizeHint())

    def selected_locations(self):
        selected = []
        _sel_model = self._locations_list.selectionModel()
        assert _sel_model is not None
        for row in _sel_model.selectedRows():
            selected.append(self.locations[row.row()])
        return selected
