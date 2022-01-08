#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import glob, os, shutil
from functools import partial
from qt.core import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, Qt, QIcon,
    QApplication, QSize, QDialogButtonBox, QTimer, QLabel, QAbstractItemView, QListView)

from calibre.constants import config_dir
from calibre.gui2 import choose_files, error_dialog
from calibre.utils.icu import sort_key


def texture_dir():
    ans = os.path.join(config_dir, 'textures')
    if not os.path.exists(ans):
        os.makedirs(ans)
    return ans


def texture_path(fname):
    if not fname:
        return
    if fname.startswith(':'):
        return I('textures/%s' % fname[1:])
    return os.path.join(texture_dir(), fname)


class TextureChooser(QDialog):

    def __init__(self, parent=None, initial=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Choose a texture'))

        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tdir = texture_dir()

        self.images = il = QListWidget(self)
        il.itemDoubleClicked.connect(self.accept, type=Qt.ConnectionType.QueuedConnection)
        il.setIconSize(QSize(256, 256))
        il.setViewMode(QListView.ViewMode.IconMode)
        il.setFlow(QListView.Flow.LeftToRight)
        il.setSpacing(20)
        il.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        il.itemSelectionChanged.connect(self.update_remove_state)
        l.addWidget(il)

        self.ad = ad = QLabel(_('The builtin textures come from <a href="{}">subtlepatterns.com</a>.').format(
            'https://www.toptal.com/designers/subtlepatterns/'))
        ad.setOpenExternalLinks(True)
        ad.setWordWrap(True)
        l.addWidget(ad)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        b = self.add_button = bb.addButton(_('Add texture'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('plus.png'))
        b.clicked.connect(self.add_texture)
        b = self.remove_button = bb.addButton(_('Remove texture'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setIcon(QIcon.ic('minus.png'))
        b.clicked.connect(self.remove_texture)
        l.addWidget(bb)

        images = [{
            'fname': ':'+os.path.basename(x),
            'path': x,
            'name': ' '.join(map(lambda s: s.capitalize(), os.path.splitext(os.path.basename(x))[0].split('_')))
        } for x in glob.glob(I('textures/*.png'))] + [{
            'fname': os.path.basename(x),
            'path': x,
            'name': os.path.splitext(os.path.basename(x))[0],
        } for x in glob.glob(os.path.join(self.tdir, '*')) if x.rpartition('.')[-1].lower() in {'jpeg', 'png', 'jpg'}]

        images.sort(key=lambda x:sort_key(x['name']))

        for i in images:
            self.create_item(i)
        self.update_remove_state()

        if initial:
            existing = {str(i.data(Qt.ItemDataRole.UserRole) or ''):i for i in (self.images.item(c) for c in range(self.images.count()))}
            item = existing.get(initial, None)
            if item is not None:
                item.setSelected(True)
                QTimer.singleShot(100, partial(il.scrollToItem, item))

        self.resize(QSize(950, 650))

    def create_item(self, data):
        x = data
        i = QListWidgetItem(QIcon(x['path']), x['name'], self.images)
        i.setData(Qt.ItemDataRole.UserRole, x['fname'])
        i.setData(Qt.ItemDataRole.UserRole+1, x['path'])
        return i

    def update_remove_state(self):
        removable = bool(self.selected_fname and not self.selected_fname.startswith(':'))
        self.remove_button.setEnabled(removable)

    @property
    def texture(self):
        return self.selected_fname

    def add_texture(self):
        path = choose_files(self, 'choose-texture-image', _('Choose image'),
                            filters=[(_('Images'), ['jpeg', 'jpg', 'png'])], all_files=False, select_only_single_file=True)
        if not path:
            return
        path = path[0]
        fname = os.path.basename(path)
        name = fname.rpartition('.')[0]
        existing = {str(i.data(Qt.ItemDataRole.UserRole) or ''):i for i in (self.images.item(c) for c in range(self.images.count()))}
        dest = os.path.join(self.tdir, fname)
        with open(path, 'rb') as s, open(dest, 'wb') as f:
            shutil.copyfileobj(s, f)
        if fname in existing:
            self.takeItem(existing[fname])
        data = {'fname': fname, 'path': dest, 'name': name}
        i = self.create_item(data)
        i.setSelected(True)
        self.images.scrollToItem(i)

    @property
    def selected_item(self):
        for x in self.images.selectedItems():
            return x

    @property
    def selected_fname(self):
        try:
            return str(self.selected_item.data(Qt.ItemDataRole.UserRole) or '')
        except (AttributeError, TypeError):
            pass

    def remove_texture(self):
        if not self.selected_fname:
            return
        if self.selected_fname.startswith(':'):
            return error_dialog(self, _('Cannot remove'),
                                _('Cannot remove builtin textures'), show=True)
        os.remove(str(self.selected_item.data(Qt.ItemDataRole.UserRole+1) or ''))
        self.images.takeItem(self.images.row(self.selected_item))


if __name__ == '__main__':
    app = QApplication([])  # noqa
    d = TextureChooser()
    d.exec()
    print(d.texture)
