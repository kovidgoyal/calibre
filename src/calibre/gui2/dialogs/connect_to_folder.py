#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QIcon,
    QItemSelectionModel,
    QLabel,
    QLineEdit,
    QSortFilterProxyModel,
    QStandardItem,
    QStandardItemModel,
    Qt,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

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
        ans = choose_dir(self, 'Select Device Folder', _('Select folder to open as device'))
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


class Model(QStandardItemModel):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        root = self.invisibleRootItem()
        man_map = {}
        for cls in usbms_plugins():
            for model in cls.model_metadata():
                man_map.setdefault(model.manufacturer_name, []).append(model)
        for manufacturer in sorted(man_map, key=primary_sort_key):
            devs = man_map[manufacturer]
            m = QStandardItem(manufacturer)
            m.setFlags(m.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            root.appendRow(m)
            devs.sort(key=lambda x: primary_sort_key(x.model_name))
            for dev in devs:
                i = QStandardItem(dev.model_name)
                i.setData(dev)
                i.setFlags(i.flags() | Qt.ItemFlag.ItemNeverHasChildren)
                m.appendRow(i)

    def itermodels(self):
        root = self.invisibleRootItem()
        for i in range(root.rowCount()):
            m = root.child(i, 0)
            for j in range(m.rowCount()):
                yield m.child(j, 0)

    def item_for_settings_key(self, q: str):
        for m in self.itermodels():
            mm = m.data()
            if mm.settings_key == q:
                return m


class ConnectToFolder(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Connect to folder'), 'connect-to-folder', parent=parent)

    def sizeHint(self):
        sz = super().sizeHint()
        sz.setWidth(max(sz.width(), 600))
        return sz

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
        self.filter_edit = fe = QLineEdit(self)
        fe.setPlaceholderText(_('Filter the device list'))
        fe.setClearButtonEnabled(True)
        l.addWidget(dg)
        l.addWidget(self.bb)
        dg.l = l = QVBoxLayout(dg)
        self.devices = d = QTreeView(self)
        self.devices_model = m = Model(d)
        self.proxy_model = p = QSortFilterProxyModel(d)
        p.setAutoAcceptChildRows(True)
        p.setRecursiveFilteringEnabled(True)
        p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        fe.textEdited.connect(self.update_filter)
        p.setSourceModel(m)
        d.setModel(p)
        d.setHeaderHidden(True)
        d.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.status_label = la3 = QLabel('')
        l.addWidget(la2)
        l.addWidget(fe)
        l.addWidget(d)
        l.addWidget(la3)

        selected_device = m.item_for_settings_key(gprefs.get('last_connected_folder_as_device', None))
        dg.setChecked(selected_device is not None)
        if selected_device is not None:
            idx = m.indexFromItem(selected_device)
            idx = p.mapFromSource(idx)
            d.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            d.scrollTo(idx)
        self.device_selection_changed()
        d.selectionModel().selectionChanged.connect(self.device_selection_changed)

    def update_filter(self):
        q = self.filter_edit.text().strip()
        self.proxy_model.setFilterFixedString(q)

    def device_selection_changed(self):
        dev = self.model_metadata
        if dev is None:
            name = _('Generic Folder device')
        else:
            name = f'{dev.manufacturer_name} {dev.model_name}'.strip()
        self.status_label.setText(_('Connecting as device: {}').format(name))

    @property
    def model_metadata(self):
        if self.devices_group.isChecked():
            for idx in self.devices.selectedIndexes():
                idx = self.proxy_model.mapToSource(idx)
                item = self.devices_model.itemFromIndex(idx)
                if item is not None:
                    return item.data()

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
