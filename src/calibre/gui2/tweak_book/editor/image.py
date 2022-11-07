#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from qt.core import (
    QMainWindow, Qt, QApplication, pyqtSignal, QLabel, QIcon, QFormLayout, QSize,
    QDialog, QSpinBox, QCheckBox, QDialogButtonBox, QToolButton, QMenu, QInputDialog)

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import actions, tprefs, editors
from calibre.gui2.tweak_book.editor.canvas import Canvas
from polyglot.builtins import itervalues


class ResizeDialog(QDialog):  # {{{

    def __init__(self, width, height, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.aspect_ratio = width / float(height)
        l.addRow(QLabel(_('Choose the new width and height')))

        self._width = w = QSpinBox(self)
        w.setMinimum(1)
        w.setMaximum(10 * width)
        w.setValue(width)
        w.setSuffix(' px')
        l.addRow(_('&Width:'), w)

        self._height = h = QSpinBox(self)
        h.setMinimum(1)
        h.setMaximum(10 * height)
        h.setValue(height)
        h.setSuffix(' px')
        l.addRow(_('&Height:'), h)
        connect_lambda(w.valueChanged, self, lambda self: self.keep_ar('width'))
        connect_lambda(h.valueChanged, self, lambda self: self.keep_ar('height'))

        self.ar = ar = QCheckBox(_('Keep &aspect ratio'))
        ar.setChecked(True)
        l.addRow(ar)
        self.resize(self.sizeHint())

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addRow(bb)

    def keep_ar(self, which):
        if self.ar.isChecked():
            val = getattr(self, which)
            oval = val / self.aspect_ratio if which == 'width' else val * self.aspect_ratio
            other = getattr(self, '_height' if which == 'width' else '_width')
            other.blockSignals(True)
            other.setValue(int(oval))
            other.blockSignals(False)

    @property
    def width(self):
        return self._width.value()

    @width.setter
    def width(self, val):
        self._width.setValue(val)

    @property
    def height(self):
        return self._height.value()

    @height.setter
    def height(self, val):
        self._height.setValue(val)
# }}}


class Editor(QMainWindow):

    has_line_numbers = False

    modification_state_changed = pyqtSignal(object)
    undo_redo_state_changed = pyqtSignal(object, object)
    data_changed = pyqtSignal(object)
    cursor_position_changed = pyqtSignal()  # dummy
    copy_available_state_changed = pyqtSignal(object)

    def __init__(self, syntax, parent=None):
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)

        self.is_synced_to_container = False
        self.syntax = syntax
        self._is_modified = False
        self.copy_available = self.cut_available = False

        self.quality = 90
        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.create_toolbars()

        self.canvas.image_changed.connect(self.image_changed)
        self.canvas.undo_redo_state_changed.connect(self.undo_redo_state_changed)
        self.canvas.selection_state_changed.connect(self.update_clipboard_actions)

    @property
    def is_modified(self):
        return self._is_modified

    @is_modified.setter
    def is_modified(self, val):
        self._is_modified = val
        self.modification_state_changed.emit(val)

    @property
    def current_editing_state(self):
        return {}

    @current_editing_state.setter
    def current_editing_state(self, val):
        pass

    @property
    def undo_available(self):
        return self.canvas.undo_action.isEnabled()

    @property
    def redo_available(self):
        return self.canvas.redo_action.isEnabled()

    @property
    def current_line(self):
        return 0

    @current_line.setter
    def current_line(self, val):
        pass

    @property
    def number_of_lines(self):
        return 0

    def pretty_print(self, name):
        return False

    def change_document_name(self, newname):
        pass

    def get_raw_data(self):
        return self.canvas.get_image_data(quality=self.quality)

    @property
    def data(self):
        return self.get_raw_data()

    @data.setter
    def data(self, val):
        self.canvas.load_image(val)
        self._is_modified = False  # The image_changed signal will have been triggered causing this editor to be incorrectly marked as modified

    def replace_data(self, raw, only_if_different=True):
        self.canvas.load_image(raw, only_if_different=only_if_different)

    def apply_settings(self, prefs=None, dictionaries_changed=False):
        pass

    def go_to_line(self, *args, **kwargs):
        pass

    def save_state(self):
        for bar in self.bars:
            if bar.isFloating():
                return
        tprefs['image-editor-state'] = bytearray(self.saveState())

    def restore_state(self):
        state = tprefs.get('image-editor-state', None)
        if state is not None:
            self.restoreState(state)

    def set_focus(self):
        self.canvas.setFocus(Qt.FocusReason.OtherFocusReason)

    def undo(self):
        self.canvas.undo_action.trigger()

    def redo(self):
        self.canvas.redo_action.trigger()

    def copy(self):
        self.canvas.copy()

    def cut(self):
        return error_dialog(self, _('Not allowed'), _(
            'Cutting of images is not allowed. If you want to delete the image, use'
            ' the files browser to do it.'), show=True)

    def paste(self):
        self.canvas.paste()

    # Search and replace {{{
    def mark_selected_text(self, *args, **kwargs):
        pass

    def find(self, *args, **kwargs):
        return False

    def replace(self, *args, **kwargs):
        return False

    def all_in_marked(self, *args, **kwargs):
        return 0

    @property
    def selected_text(self):
        return ''
    # }}}

    def image_changed(self, new_image):
        self.is_synced_to_container = False
        self._is_modified = True
        self.copy_available = self.canvas.is_valid
        self.copy_available_state_changed.emit(self.copy_available)
        self.data_changed.emit(self)
        self.modification_state_changed.emit(True)
        self.fmt_label.setText(' ' + (self.canvas.original_image_format or '').upper())
        im = self.canvas.current_image
        self.size_label.setText('{} x {}{}'.format(im.width(), im.height(), ' px'))

    def break_cycles(self):
        self.canvas.break_cycles()
        self.canvas.image_changed.disconnect()
        self.canvas.undo_redo_state_changed.disconnect()
        self.canvas.selection_state_changed.disconnect()

        self.modification_state_changed.disconnect()
        self.undo_redo_state_changed.disconnect()
        self.data_changed.disconnect()
        self.cursor_position_changed.disconnect()
        self.copy_available_state_changed.disconnect()

    def contextMenuEvent(self, ev):
        ev.ignore()

    def create_toolbars(self):
        self.action_bar = b = self.addToolBar(_('File actions tool bar'))
        b.setObjectName('action_bar')  # Needed for saveState
        for x in ('undo', 'redo'):
            b.addAction(getattr(self.canvas, '%s_action' % x))
        self.edit_bar = b = self.addToolBar(_('Edit actions tool bar'))
        b.setObjectName('edit-actions-bar')
        for x in ('copy', 'paste'):
            ac = actions['editor-%s' % x]
            setattr(self, 'action_' + x, b.addAction(ac.icon(), x, getattr(self, x)))
        self.update_clipboard_actions()

        b.addSeparator()
        self.action_trim = ac = b.addAction(QIcon.ic('trim.png'), _('Trim image'), self.canvas.trim_image)
        self.action_rotate = ac = b.addAction(QIcon.ic('rotate-right.png'), _('Rotate image'), self.canvas.rotate_image)
        self.action_resize = ac = b.addAction(QIcon.ic('resize.png'), _('Resize image'), self.resize_image)
        b.addSeparator()
        self.action_filters = ac = b.addAction(QIcon.ic('filter.png'), _('Image filters'))
        b.widgetForAction(ac).setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.filters_menu = m = QMenu(self)
        ac.setMenu(m)
        m.addAction(_('Auto-trim image'), self.canvas.autotrim_image)
        m.addAction(_('Sharpen image'), self.sharpen_image)
        m.addAction(_('Blur image'), self.blur_image)
        m.addAction(_('De-speckle image'), self.canvas.despeckle_image)
        m.addAction(_('Improve contrast (normalize image)'), self.canvas.normalize_image)
        m.addAction(_('Make image look like an oil painting'), self.oilify_image)

        self.info_bar = b = self.addToolBar(_('Image information bar'))
        b.setObjectName('image_info_bar')
        self.fmt_label = QLabel('')
        b.addWidget(self.fmt_label)
        b.addSeparator()
        self.size_label = QLabel('')
        b.addWidget(self.size_label)
        self.bars = [self.action_bar, self.edit_bar, self.info_bar]
        for x in self.bars:
            x.setFloatable(False)
            x.topLevelChanged.connect(self.toolbar_floated)
            x.setIconSize(QSize(tprefs['toolbar_icon_size'], tprefs['toolbar_icon_size']))
        self.restore_state()

    def toolbar_floated(self, floating):
        if not floating:
            self.save_state()
            for ed in itervalues(editors):
                if ed is not self:
                    ed.restore_state()

    def update_clipboard_actions(self, *args):
        if self.canvas.has_selection:
            self.action_copy.setText(_('Copy selected region'))
            self.action_paste.setText(_('Paste into selected region'))
        else:
            self.action_copy.setText(_('Copy image'))
            self.action_paste.setText(_('Paste image'))

    def resize_image(self):
        im = self.canvas.current_image
        d = ResizeDialog(im.width(), im.height(), self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.canvas.resize_image(d.width, d.height)

    def sharpen_image(self):
        val, ok = QInputDialog.getInt(self, _('Sharpen image'), _(
            'The standard deviation for the Gaussian sharpen operation (higher means more sharpening)'), value=3, min=1, max=20)
        if ok:
            self.canvas.sharpen_image(sigma=val)

    def blur_image(self):
        val, ok = QInputDialog.getInt(self, _('Blur image'), _(
            'The standard deviation for the Gaussian blur operation (higher means more blurring)'), value=3, min=1, max=20)
        if ok:
            self.canvas.blur_image(sigma=val)

    def oilify_image(self):
        val, ok = QInputDialog.getDouble(self, _('Oilify image'), _(
            'The strength of the operation (higher numbers have larger effects)'), value=4, min=0.1, max=20)
        if ok:
            self.canvas.oilify_image(radius=val)


def launch_editor(path_to_edit, path_is_raw=False):
    app = QApplication([])
    if path_is_raw:
        raw = path_to_edit
    else:
        with open(path_to_edit, 'rb') as f:
            raw = f.read()
    t = Editor('raster_image')
    t.data = raw
    t.show()
    app.exec()


if __name__ == '__main__':
    launch_editor(sys.argv[-1])
