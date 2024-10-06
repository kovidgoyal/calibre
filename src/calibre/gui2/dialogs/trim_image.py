#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import sys

from qt.core import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QSize,
    QSpinBox,
    Qt,
    QToolBar,
    QVBoxLayout,
)

from calibre.gui2 import gprefs
from calibre.gui2.tweak_book.editor.canvas import Canvas


def reduce_to_ratio(w, h, r):
    h = min(h, w / r)
    w = r * h
    return int(round(w)), int(round(h))


class Region(QDialog):

    ignore_value_changes = False

    def __init__(self, parent, width, height, max_width, max_height):
        super().__init__(parent)
        self.setWindowTitle(_('Set size of selected area'))
        self.l = l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.width_input = w = QSpinBox(self)
        w.setRange(20, max_width), w.setSuffix(' px'), w.setValue(width)
        w.valueChanged.connect(self.value_changed)
        l.addRow(_('&Width:'), w)
        self.height_input = h = QSpinBox(self)
        h.setRange(20, max_height), h.setSuffix(' px'), h.setValue(height)
        h.valueChanged.connect(self.value_changed)
        l.addRow(_('&Height:'), h)
        self.ratio_input = r = QDoubleSpinBox(self)
        r.setRange(0.0, 5.00), r.setDecimals(2), r.setValue(max_width/max_height), r.setSingleStep(0.01)
        r.setToolTip(_('For example, use 0.75 for kindle devices.'))
        self.m_width = max_width
        self.m_height = max_height
        r.valueChanged.connect(self.aspect_changed)
        l.addRow(_('&Aspect ratio:'), r)
        self.const_aspect = ca = QCheckBox(_('Keep the ratio of width to height fixed'))
        ca.toggled.connect(self.const_aspect_toggled)
        l.addRow(ca)
        k = QKeySequence('alt+1', QKeySequence.SequenceFormat.PortableText).toString(QKeySequence.SequenceFormat.NativeText).partition('+')[0]
        la = QLabel('<p>'+_('Note that holding down the {} key while dragging the selection handles'
                          ' will resize the selection while preserving its aspect ratio.').format(k))
        la.setWordWrap(True)
        la.setMinimumWidth(400)
        l.addRow(la)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addRow(bb)
        self.resize(self.sizeHint())
        self.current_aspect = width / height
        self.ratio_input.setEnabled(not self.const_aspect.isChecked())

    def aspect_changed(self):
        inp = float(self.ratio_input.value())
        if inp > 0 and inp != round(self.m_width/self.m_height, 2):
            rw, rh = reduce_to_ratio(self.m_width, self.m_height, inp)
            self.width_input.setValue(rw)
            self.height_input.setValue(rh)
        else:
            self.width_input.setValue(self.m_width)
            self.height_input.setValue(self.m_height)

    def const_aspect_toggled(self):
        self.ratio_input.setEnabled(not self.const_aspect.isChecked())
        if self.const_aspect.isChecked():
            self.current_aspect = self.width_input.value() / self.height_input.value()

    def value_changed(self):
        if self.ignore_value_changes or not self.const_aspect.isChecked():
            return
        src = self.sender()
        self.ignore_value_changes = True
        if src is self.height_input:
            self.width_input.setValue(int(self.current_aspect * self.height_input.value()))
        else:
            self.height_input.setValue(int(self.width_input.value() / self.current_aspect))
        self.ignore_value_changes = False

    @property
    def selection_size(self):
        return self.width_input.value(), self.height_input.value()


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
        self.size_selection = ac = self.bar.addAction(QIcon.ic('resize.png'), _('&Region'), self.do_region)
        ac.setToolTip(_('Specify a selection region size using numbers to allow for precise control'))
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

    def do_region(self):
        rect = self.canvas.selection_rect_in_image_coords
        d = Region(self, int(rect.width()), int(rect.height()), self.canvas.current_image.width(), self.canvas.current_image.height())
        if d.exec() == QDialog.DialogCode.Accepted:
            width, height = d.selection_size
            self.canvas.set_selection_size_in_image_coords(width, height)

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
