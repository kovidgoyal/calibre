#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QMainWindow, Qt, QApplication

from calibre.gui2.tweak_book.editor.text import TextEdit

class Editor(QMainWindow):

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.Widget)
        self.editor = TextEdit(self)
        self.setCentralWidget(self.editor)

    def load_text(self, raw, syntax='html'):
        self.editor.load_text(raw, syntax=syntax)

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
    t = Editor()
    t.load_text(raw, syntax=syntax)
    t.show()
    app.exec_()

