#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QAbstractItemView, QGroupBox, QHBoxLayout, QIcon, QLabel, Qt, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from calibre.customize.ui import usbms_plugins
from calibre.gui2 import Application, choose_dir, gprefs
from calibre.gui2.widgets2 import Dialog, HistoryLineEdit2
from calibre.utils.icu import primary_sort_key


class ChooseFolder(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_edit = fe = HistoryLineEdit2(parent=self)
        fe.initialize('connect-to-folder')
        fe.setPlaceholderText(_('Path to folder to connect to'))
        if len(fe.history):
            fe.setText(fe.history[0])
        self.browse_button = bb = QToolButton(self)
        bb.setIcon(QIcon.ic('mimetypes/dir.png'))
        bb.clicked.connect(self.browse)
        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(fe)
        l.addWidget(bb)

    def browse(self):
        ans = choose_dir(self, 'connect-to-folder-browse-history', _('Choose folder to connect to'))
        if ans:
            self.folder_edit.setText(ans)

    @property
    def folder(self):
        return self.folder_edit.text().strip()

    @folder.setter
    def folder(self, val):
        self.folder_edit.setText((val or '').strip())

    def on_accept(self):
        if self.folder:
            self.folder_edit.save_history()


class ConnectToFolder(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Connect to folder'), 'connect-to-folder', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.folder_chooser = fc = ChooseFolder(self)
        l.addWidget(fc)
        self.la = la = QLabel('<p>' + _(
            'Choose a device to connect as below. If no device is chosen a generic <i>Folder device</i>'
            ' will be used.'))
        self.la2 = la2 = QLabel('<p>' + _('<b>WARNING</b>: Connecting as a specific device will work only'
            ' if the chosen folder above contains the actual files from an actual device, as the'
            ' device drivers often expect to find certain device specific files. So only choose'
            ' a device below if you have copied the files from a real device or mounted it at the'
            ' chosen location.'))
        la.setWordWrap(True), la2.setWordWrap(True)
        l.addWidget(la)
        self.devices_group = dg = QGroupBox(_('Connect as device'), self)
        dg.setCheckable(True)
        l.addWidget(dg)
        l.addWidget(self.bb)
        dg.l = l = QVBoxLayout(dg)
        self.devices = d = QTreeWidget(self)
        d.setHeaderHidden(True)
        d.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        l.addWidget(la2)
        l.addWidget(d)

        lcd = gprefs.get('last_connected_folder_as_device', None)
        selected_device = None
        man_map = {}
        for cls in usbms_plugins():
            for model in cls.model_metadata():
                man_map.setdefault(model.manufacturer_name, []).append(model)
        for manufacturer in sorted(man_map, key=primary_sort_key):
            devs = man_map[manufacturer]
            m = QTreeWidgetItem(d, 0)
            m.setText(0, manufacturer)
            m.setFlags(m.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            flags = m.flags()
            devs.sort(key=lambda x: primary_sort_key(x.model_name))
            expanded = False
            for dev in devs:
                i = QTreeWidgetItem(m, 1)
                i.setText(0, dev.model_name)
                i.setData(0, Qt.ItemDataRole.UserRole, dev)
                i.setFlags(i.flags() | Qt.ItemFlag.ItemNeverHasChildren)
                if dev.settings_key == lcd:
                    i.setSelected(True)
                    expanded = True
                    selected_device = i
            m.setExpanded(expanded)
        if selected_device is not None:
            d.scrollToItem(selected_device)
        dg.setChecked(selected_device is not None)

    @property
    def model_metadata(self):
        if self.devices_group.isChecked():
            for m in range(self.devices.topLevelItemCount()):
                man = self.devices.topLevelItem(m)
                for i in range(man.childCount()):
                    item = man.child(i)
                    if item.isSelected():
                        return item.data(0, Qt.ItemDataRole.UserRole)

    def accept(self):
        self.folder_chooser.on_accept()
        m = self.model_metadata
        gprefs.set('last_connected_folder_as_device', None if m is None else m.settings_key)
        return super().accept()

    @property
    def ans(self):
        return self.folder_chooser.folder, self.model_metadata


if __name__ == '__main__':
    app = Application([])
    d = ConnectToFolder()
    d.exec()
    print(d.ans)
