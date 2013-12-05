#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt4.Qt import (
    QMainWindow, Qt, QApplication, pyqtSignal)

from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import actions
from calibre.gui2.tweak_book.editor.canvas import Canvas

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
            self.setWindowFlags(Qt.Widget)

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

    @dynamic_property
    def is_modified(self):
        def fget(self):
            return self._is_modified
        def fset(self, val):
            self._is_modified = val
            self.modification_state_changed.emit(val)
        return property(fget=fget, fset=fset)

    @property
    def undo_available(self):
        return self.canvas.undo_action.isEnabled()

    @property
    def redo_available(self):
        return self.canvas.redo_action.isEnabled()

    @dynamic_property
    def current_line(self):
        def fget(self):
            return 0
        def fset(self, val):
            pass
        return property(fget=fget, fset=fset)

    @property
    def number_of_lines(self):
        return 0

    def get_raw_data(self):
        return self.canvas.get_image_data(quality=self.quality)

    @dynamic_property
    def data(self):
        def fget(self):
            return self.get_raw_data()
        def fset(self, val):
            self.canvas.load_image(val)
        return property(fget=fget, fset=fset)

    def replace_data(self, raw, only_if_different=True):
        # We ignore only_if_different as it is useless in our case, and
        # there is no easy way to check two images for equality
        self.data = raw

    def apply_settings(self, prefs=None):
        pass

    def set_focus(self):
        self.canvas.setFocus(Qt.OtherFocusReason)

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
        for x in ('copy', 'paste'):
            try:
                ac = actions['editor-%s' % x]
            except KeyError:
                b.addAction(x, getattr(self.canvas, x))
            else:
                setattr(self, 'action_' + x, b.addAction(ac.icon(), x, getattr(self, x)))
        self.update_clipboard_actions()

    def update_clipboard_actions(self, *args):
        if self.canvas.has_selection:
            self.action_copy.setText(_('Copy selected region'))
            self.action_paste.setText(_('Paste into selected region'))
        else:
            self.action_copy.setText(_('Copy image'))
            self.action_paste.setText(_('Paste image'))

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
    app.exec_()

if __name__ == '__main__':
    launch_editor(sys.argv[-1])
