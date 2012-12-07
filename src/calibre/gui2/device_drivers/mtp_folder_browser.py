#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from operator import attrgetter

from PyQt4.Qt import (QTabWidget, QTreeWidget, QTreeWidgetItem, Qt, QDialog,
        QDialogButtonBox, QVBoxLayout, QSize, pyqtSignal, QIcon)

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

def browse():
    from calibre.gui2 import Application
    from calibre.devices.mtp.driver import MTP_DEVICE
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    app = Application([])
    app
    dev = MTP_DEVICE(None)
    dev.startup()
    cd = dev.detect_managed_devices(s.devices)
    if cd is None:
        raise ValueError('No MTP device found')
    dev.open(cd, 'test')
    d = Browser(dev.filesystem_cache)
    d.exec_()
    dev.shutdown()
    return d.current_item

if __name__ == '__main__':
    print (browse())

