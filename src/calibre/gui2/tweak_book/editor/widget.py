#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QMainWindow, Qt, QApplication, pyqtSignal

from calibre import xml_replace_entities
from calibre.gui2.tweak_book import actions
from calibre.gui2.tweak_book.editor.text import TextEdit

class Editor(QMainWindow):

    modification_state_changed = pyqtSignal(object)
    undo_redo_state_changed = pyqtSignal(object, object)
    copy_available_state_changed = pyqtSignal(object)
    data_changed = pyqtSignal(object)

    def __init__(self, syntax, parent=None):
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.Widget)
        self.syntax = syntax
        self.editor = TextEdit(self)
        self.setCentralWidget(self.editor)
        self.editor.modificationChanged.connect(self.modification_state_changed.emit)
        self.create_toolbars()
        self.undo_available = False
        self.redo_available = False
        self.copy_available = self.cut_available = False
        self.editor.undoAvailable.connect(self._undo_available)
        self.editor.redoAvailable.connect(self._redo_available)
        self.editor.textChanged.connect(self._data_changed)
        self.editor.copyAvailable.connect(self._copy_available)

    @dynamic_property
    def data(self):
        def fget(self):
            ans = unicode(self.editor.toPlainText())
            if self.syntax == 'html':
                ans = xml_replace_entities(ans)
            return ans.encode('utf-8')
        def fset(self, val):
            self.editor.load_text(val, syntax=self.syntax)
        return property(fget=fget, fset=fset)

    def get_raw_data(self):
        return unicode(self.editor.toPlainText())

    def undo(self):
        self.editor.undo()

    def redo(self):
        self.editor.redo()

    @dynamic_property
    def is_modified(self):
        def fget(self):
            return self.editor.is_modified
        def fset(self, val):
            self.editor.is_modified = val
        return property(fget=fget, fset=fset)

    def create_toolbars(self):
        self.action_bar = b = self.addToolBar(_('File actions tool bar'))
        b.setObjectName('action_bar')  # Needed for saveState
        for x in ('save', 'undo', 'redo'):
            b.addAction(actions['editor-%s' % x])
        self.edit_bar = b = self.addToolBar(_('Edit actions tool bar'))
        for x in ('cut', 'copy', 'paste'):
            b.addAction(actions['editor-%s' % x])

    def break_cycles(self):
        self.modification_state_changed.disconnect()
        self.undo_redo_state_changed.disconnect()
        self.copy_available_state_changed.disconnect()
        self.data_changed.disconnect()
        self.editor.undoAvailable.disconnect()
        self.editor.redoAvailable.disconnect()
        self.editor.modificationChanged.disconnect()
        self.editor.textChanged.disconnect()
        self.editor.copyAvailable.disconnect()
        self.editor.setPlainText('')

    def _data_changed(self):
        self.data_changed.emit(self)

    def _undo_available(self, available):
        self.undo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _redo_available(self, available):
        self.redo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _copy_available(self, available):
        self.copy_available = self.cut_available = available
        self.copy_available_state_changed.emit(available)

    def cut(self):
        self.editor.cut()

    def copy(self):
        self.editor.copy()

    def paste(self):
        self.editor.paste()


def launch_editor(path_to_edit, path_is_raw=False, syntax='html'):
    if path_is_raw:
        raw = path_to_edit
    else:
        with open(path_to_edit, 'rb') as f:
            raw = f.read().decode('utf-8')
        ext = path_to_edit.rpartition('.')[-1].lower()
        if ext in ('html', 'htm', 'xhtml', 'xhtm'):
            syntax = 'html'
        elif ext in ('css',):
            syntax = 'css'
    app = QApplication([])
    t = Editor(syntax)
    t.load_text(raw, syntax=syntax)
    t.show()
    app.exec_()

