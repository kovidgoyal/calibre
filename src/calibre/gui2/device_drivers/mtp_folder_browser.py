#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt4.Qt import (QTabWidget, QTreeWidget, QTreeWidgetItem, Qt, QDialog,
        QDialogButtonBox, QVBoxLayout, QSize, pyqtSignal, QIcon, QLabel,
        QListWidget, QListWidgetItem)

from calibre.gui2 import file_icon_provider

def item(f, parent):
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

    def __init__(self, storage, show_files):
        QTreeWidget.__init__(self)
        self.show_files = show_files
        self.create_children(storage, self)
        self.name = storage.name
        self.object_id = storage.persistent_id
        self.setMinimumHeight(350)
        self.setHeaderHidden(True)

    def create_children(self, f, parent):
        for child in sorted(f.folders, key=attrgetter('name')):
            i = item(child, parent)
            self.create_children(child, i)
        if self.show_files:
            for child in sorted(f.files, key=attrgetter('name')):
                i = item(child, parent)

    @property
    def current_item(self):
        item = self.currentItem()
        if item is not None:
            return (self.object_id, item.data(0, Qt.UserRole).toPyObject())
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

class TopLevel(QDialog):

    def __init__(self, dev, ignored_folders=None, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel('<p>'+ _('<b>Scanned folders:</b>') + ' ' +
            _('You can select which top level folders calibre will '
              'scan when searching this device for books.'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.tabs = QTabWidget(self)
        l.addWidget(self.tabs)
        self.widgets = []

        for storage in dev.filesystem_cache.entries:
            w = QListWidget(self)
            w.storage = storage
            self.tabs.addTab(w, storage.name)
            self.widgets.append(w)
            for child in sorted(storage.folders, key=attrgetter('name')):
                i = QListWidgetItem(child.name)
                i.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                i.setCheckState(Qt.Unchecked if
                    dev.is_folder_ignored(storage, child.name,
                            ignored_folders=ignored_folders) else Qt.Checked)
                w.addItem(i)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok |
                                   QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.sab = self.bb.addButton(_('Select &All'), self.bb.ActionRole)
        self.sab.clicked.connect(self.select_all)
        self.snb = self.bb.addButton(_('Select &None'), self.bb.ActionRole)
        self.snb.clicked.connect(self.select_none)
        l.addWidget(self.bb)
        self.setWindowTitle(_('Choose folders to scan'))
        self.setWindowIcon(QIcon(I('devices/tablet.png')))

        self.resize(500, 500)

    def select_all(self):
        w = self.tabs.currentWidget()
        for i in xrange(w.count()):
            x = w.item(i)
            x.setCheckState(Qt.Checked)

    def select_none(self):
        w = self.tabs.currentWidget()
        for i in xrange(w.count()):
            x = w.item(i)
            x.setCheckState(Qt.Unchecked)

    @property
    def ignored_folders(self):
        ans = {}
        for w in self.widgets:
            ans[unicode(w.storage.object_id)] = folders = []
            for i in xrange(w.count()):
                x = w.item(i)
                if x.checkState() != Qt.Checked:
                    folders.append(unicode(x.text()))
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

def top_level():
    from calibre.gui2 import Application
    app = Application([])
    app
    dev = setup_device()
    d = TopLevel(dev, None)
    d.exec_()
    dev.shutdown()
    return d.ignored_folders

if __name__ == '__main__':
    # print (browse())
    print ('Ignored:', top_level())

