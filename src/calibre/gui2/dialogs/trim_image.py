#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import sys
from qt.core import (
    QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QKeySequence,
    QLabel, QSize, Qt, QToolBar, QVBoxLayout
)

from calibre.gui2 import gprefs
from calibre.gui2.tweak_book.editor.canvas import Canvas


class TrimImage(QDialog):

    def __init__(self, img_data, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setWindowTitle(_('Trim Image'))

        self.bar = b = QToolBar(self)
        l.addWidget(b)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setIconSize(QSize(32, 32))

        self.msg = la = QLabel('\xa0' + _(
            'Select a region by dragging with your mouse, and then click trim'))
        self.msg_txt = self.msg.text()
        self.sz = QLabel('')

        self.canvas = c = Canvas(self)
        c.image_changed.connect(self.image_changed)
        c.load_image(img_data)
        self.undo_action = u = c.undo_action
        u.setShortcut(QKeySequence(QKeySequence.StandardKey.Undo))
        self.redo_action = r = c.redo_action
        r.setShortcut(QKeySequence(QKeySequence.StandardKey.Redo))
        self.trim_action = ac = self.bar.addAction(QIcon.ic('trim.png'), _('&Trim'), self.do_trim)
        ac.setShortcut(QKeySequence('Ctrl+T'))
        ac.setToolTip('{} [{}]'.format(_('Trim image by removing borders outside the selected region'),
                                   ac.shortcut().toString(QKeySequence.SequenceFormat.NativeText)))
        ac.setEnabled(False)
        c.selection_state_changed.connect(self.selection_changed)
        c.selection_area_changed.connect(self.selection_area_changed)
        l.addWidget(c)
        self.bar.addAction(self.trim_action)
        self.bar.addSeparator()
        self.bar.addAction(u)
        self.bar.addAction(r)
        self.bar.addSeparator()
        self.bar.addWidget(la)
        self.bar.addSeparator()
        self.bar.addWidget(self.sz)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        h = QHBoxLayout()
        l.addLayout(h)
        self.tr_sz = QLabel('')
        h.addWidget(self.tr_sz)
        h.addStretch(10)
        h.addWidget(bb)

        self.restore_geometry(gprefs, 'image-trim-dialog-geometry')
        self.setWindowIcon(self.trim_action.icon())
        self.image_data = None

    def sizeHint(self):
        return QSize(900, 600)

    def do_trim(self):
        self.canvas.trim_image()
        self.selection_changed(False)

    def selection_changed(self, has_selection):
        self.trim_action.setEnabled(has_selection)
        self.msg.setText(_('Adjust selection by dragging corners') if has_selection else self.msg_txt)

    def selection_area_changed(self, rect):
        if rect:
            x, y, w, h = map(int, self.canvas.rect_for_trim())
            text = f'{int(w)}x{int(h)}'
            text = _('Size: {0}px Aspect ratio: {1:.3g}').format(text, w / h)
        else:
            text = ''
        self.tr_sz.setText(text)

    def image_changed(self, qimage):
        self.sz.setText('\xa0' + _('Size: {0}x{1}px').format(qimage.width(), qimage.height()))

    def cleanup(self):
        self.canvas.break_cycles()
        self.save_geometry(gprefs, 'image-trim-dialog-geometry')

    def accept(self):
        if self.trim_action.isEnabled():
            self.trim_action.trigger()
        if self.canvas.is_modified:
            self.image_data = self.canvas.get_image_data()
        self.cleanup()
        QDialog.accept(self)

    def reject(self):
        self.cleanup()
        QDialog.reject(self)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    fname = sys.argv[-1]
    with open(fname, 'rb') as f:
        data = f.read()
    d = TrimImage(data)
    if d.exec() == QDialog.DialogCode.Accepted and d.image_data is not None:
        b, ext = os.path.splitext(fname)
        fname = b + '-trimmed' + ext
        with open(fname, 'wb') as f:
            f.write(d.image_data)
        print('Trimmed image written to', fname)
