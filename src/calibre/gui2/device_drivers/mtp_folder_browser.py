#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt5.Qt import (QTabWidget, QTreeWidget, QTreeWidgetItem, Qt, QDialog,
        QDialogButtonBox, QVBoxLayout, QSize, pyqtSignal, QIcon, QLabel)

from calibre.gui2 import file_icon_provider
from polyglot.builtins import unicode_type, range


def browser_item(f, parent):
    name = f.name
    if not f.is_folder:
        name += ' [%s]'%f.last_mod_string
    ans = QTreeWidgetItem(parent, [name])
    ans.setData(0, Qt.UserRole, f.full_path)
    if f.is_folder:
        ext = 'dir'
    else:
        ext = f.name.rpartition('.')[-1]
    ans.setData(0, Qt.DecorationRole, file_icon_provider().icon_from_ext(ext))

    return ans


class Storage(QTreeWidget):

    def __init__(self, storage, show_files=False, item_func=browser_item):
        QTreeWidget.__init__(self)
        self.item_func = item_func
        self.show_files = show_files
        self.create_children(storage, self)
        self.name = storage.name
        self.object_id = storage.persistent_id
        self.setMinimumHeight(350)
        self.setHeaderHidden(True)
        self.storage = storage

    def create_children(self, f, parent):
        for child in sorted(f.folders, key=attrgetter('name')):
            i = self.item_func(child, parent)
            self.create_children(child, i)
        if self.show_files:
            for child in sorted(f.files, key=attrgetter('name')):
                i = self.item_func(child, parent)

    @property
    def current_item(self):
        item = self.currentItem()
        if item is not None:
            return (self.object_id, item.data(0, Qt.UserRole))
        return None


class Folders(QTabWidget):

    selected = pyqtSignal()

    def __init__(self, filesystem_cache, show_files=True):
        QTabWidget.__init__(self)
        self.fs = filesystem_cache
        for storage in self.fs.entries:
            w = Storage(storage, show_files)
            self.addTab(w, w.name)
            w.doubleClicked.connect(self.selected)

        self.setCurrentIndex(0)

    @property
    def current_item(self):
        w = self.currentWidget()
        if w is not None:
            return w.current_item


class Browser(QDialog):

    def __init__(self, filesystem_cache, show_files=True, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.folders = cw = Folders(filesystem_cache, show_files=show_files)
        l.addWidget(cw)
        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.setMinimumSize(QSize(500, 500))
        self.folders.selected.connect(self.accept)
        self.setWindowTitle(_('Choose folder on device'))
        self.setWindowIcon(QIcon(I('devices/tablet.png')))

    @property
    def current_item(self):
        return self.folders.current_item


class IgnoredFolders(QDialog):

    def __init__(self, dev, ignored_folders=None, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel('<p>'+ _('<b>Scanned folders:</b>') + ' ' +
            _('You can select which folders calibre will '
              'scan when searching this device for books.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.tabs = QTabWidget(self)
        l.addWidget(self.tabs)
        self.widgets = []

        for storage in dev.filesystem_cache.entries:
            self.dev = dev
            w = Storage(storage, item_func=self.create_item)
            del self.dev
            self.tabs.addTab(w, storage.name)
            self.widgets.append(w)
            w.itemChanged.connect(self.item_changed)

        self.la2 = la = QLabel(_(
            'If you a select a previously unselected folder, any sub-folders'
            ' will not be visible until you restart calibre.'))
        l.addWidget(la)
        la.setWordWrap(True)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok |
                                   QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.sab = self.bb.addButton(_('Select &all'), self.bb.ActionRole)
        self.sab.clicked.connect(self.select_all)
        self.snb = self.bb.addButton(_('Select &none'), self.bb.ActionRole)
        self.snb.clicked.connect(self.select_none)
        l.addWidget(self.bb)
        self.setWindowTitle(_('Choose folders to scan'))
        self.setWindowIcon(QIcon(I('devices/tablet.png')))

        self.resize(600, 500)

    def item_changed(self, item, column):
        w = item.treeWidget()
        root = w.invisibleRootItem()
        w.itemChanged.disconnect(self.item_changed)
        try:
            if item.checkState(0) == Qt.Checked:
                # Ensure that the parents of this item are checked
                p = item.parent()
                while p is not None and p is not root:
                    p.setCheckState(0, Qt.Checked)
                    p = p.parent()
            # Set the state of all descendants to the same state as this item
            for child in self.iterchildren(item):
                child.setCheckState(0, item.checkState(0))
        finally:
            w.itemChanged.connect(self.item_changed)

    def iterchildren(self, node):
        ' Iterate over all descendants of node '
        for i in range(node.childCount()):
            child = node.child(i)
            yield child
            for gc in self.iterchildren(child):
                yield gc

    def create_item(self, f, parent):
        name = f.name
        ans = QTreeWidgetItem(parent, [name])
        ans.setData(0, Qt.UserRole, '/'.join(f.full_path[1:]))
        ans.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        ans.setCheckState(0,
            Qt.Unchecked if self.dev.is_folder_ignored(f.storage_id, f.full_path[1:]) else Qt.Checked)
        ans.setData(0, Qt.DecorationRole, file_icon_provider().icon_from_ext('dir'))
        return ans

    def select_all(self):
        w = self.tabs.currentWidget()
        for i in range(w.invisibleRootItem().childCount()):
            c = w.invisibleRootItem().child(i)
            c.setCheckState(0, Qt.Checked)

    def select_none(self):
        w = self.tabs.currentWidget()
        for i in range(w.invisibleRootItem().childCount()):
            c = w.invisibleRootItem().child(i)
            c.setCheckState(0, Qt.Unchecked)

    @property
    def ignored_folders(self):
        ans = {}
        for w in self.widgets:
            folders = set()
            for node in self.iterchildren(w.invisibleRootItem()):
                if node.checkState(0) == Qt.Checked:
                    continue
                path = unicode_type(node.data(0, Qt.UserRole) or '')
                parent = path.rpartition('/')[0]
                if '/' not in path or icu_lower(parent) not in folders:
                    folders.add(icu_lower(path))
            ans[unicode_type(w.storage.storage_id)] = list(folders)
        return ans


def setup_device():
    from calibre.devices.mtp.driver import MTP_DEVICE
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    dev = MTP_DEVICE(None)
    dev.startup()
    cd = dev.detect_managed_devices(s.devices)
    if cd is None:
        raise ValueError('No MTP device found')
    dev.open(cd, 'test')
    return dev


def browse():
    from calibre.gui2 import Application
    app = Application([])
    app
    dev = setup_device()
    d = Browser(dev.filesystem_cache)
    d.exec_()
    dev.shutdown()
    return d.current_item


def ignored_folders():
    from calibre.gui2 import Application
    app = Application([])
    app
    dev = setup_device()
    d = IgnoredFolders(dev)
    d.exec_()
    dev.shutdown()
    return d.ignored_folders


if __name__ == '__main__':
    print(browse())
    # print ('Ignored:', ignored_folders())
