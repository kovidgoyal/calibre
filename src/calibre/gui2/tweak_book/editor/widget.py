#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import unicodedata

from PyQt4.Qt import QMainWindow, Qt, QApplication, pyqtSignal

from calibre import xml_replace_entities
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import actions, current_container
from calibre.gui2.tweak_book.editor.text import TextEdit

class Editor(QMainWindow):

    has_line_numbers = True

    modification_state_changed = pyqtSignal(object)
    undo_redo_state_changed = pyqtSignal(object, object)
    copy_available_state_changed = pyqtSignal(object)
    data_changed = pyqtSignal(object)
    cursor_position_changed = pyqtSignal()

    def __init__(self, syntax, parent=None):
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.Widget)
        self.is_synced_to_container = False
        self.syntax = syntax
        self.editor = TextEdit(self)
        self.setCentralWidget(self.editor)
        self.create_toolbars()
        self.undo_available = False
        self.redo_available = False
        self.copy_available = self.cut_available = False
        self.editor.modificationChanged.connect(self._modification_state_changed)
        self.editor.undoAvailable.connect(self._undo_available)
        self.editor.redoAvailable.connect(self._redo_available)
        self.editor.textChanged.connect(self._data_changed)
        self.editor.copyAvailable.connect(self._copy_available)
        self.editor.cursorPositionChanged.connect(self._cursor_position_changed)

    @dynamic_property
    def current_line(self):
        def fget(self):
            return self.editor.textCursor().blockNumber()
        def fset(self, val):
            self.editor.go_to_line(val)
        return property(fget=fget, fset=fset)

    @property
    def number_of_lines(self):
        return self.editor.blockCount()

    @dynamic_property
    def data(self):
        def fget(self):
            ans = self.get_raw_data()
            if self.syntax == 'html':
                ans = xml_replace_entities(ans)
            return ans.encode('utf-8')
        def fset(self, val):
            self.editor.load_text(val, syntax=self.syntax)
        return property(fget=fget, fset=fset)

    def init_from_template(self, template):
        self.editor.load_text(template, syntax=self.syntax, process_template=True)

    def get_raw_data(self):
        return unicodedata.normalize('NFC', unicode(self.editor.toPlainText()))

    def replace_data(self, raw, only_if_different=True):
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        current = self.get_raw_data() if only_if_different else False
        if current != raw:
            self.editor.replace_text(raw)

    def apply_settings(self, prefs=None):
        self.editor.apply_settings(prefs=None)

    def set_focus(self):
        self.editor.setFocus(Qt.OtherFocusReason)

    def undo(self):
        self.editor.undo()

    def redo(self):
        self.editor.redo()

    @property
    def selected_text(self):
        return self.editor.selected_text

    # Search and replace {{{
    def mark_selected_text(self):
        self.editor.mark_selected_text()

    def find(self, *args, **kwargs):
        return self.editor.find(*args, **kwargs)

    def replace(self, *args, **kwargs):
        return self.editor.replace(*args, **kwargs)

    def all_in_marked(self, *args, **kwargs):
        return self.editor.all_in_marked(*args, **kwargs)

    def go_to_anchor(self, *args, **kwargs):
        return self.editor.go_to_anchor(*args, **kwargs)
    # }}}

    @property
    def has_marked_text(self):
        return self.editor.current_search_mark is not None

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
        for x in ('undo', 'redo'):
            b.addAction(actions['editor-%s' % x])
        self.edit_bar = b = self.addToolBar(_('Edit actions tool bar'))
        for x in ('cut', 'copy', 'paste'):
            b.addAction(actions['editor-%s' % x])
        self.tools_bar = b = self.addToolBar(_('Editor tools'))
        if self.syntax == 'html':
            b.addAction(actions['fix-html-current'])
        if self.syntax in {'xml', 'html', 'css'}:
            b.addAction(actions['pretty-current'])

    def break_cycles(self):
        self.modification_state_changed.disconnect()
        self.undo_redo_state_changed.disconnect()
        self.copy_available_state_changed.disconnect()
        self.cursor_position_changed.disconnect()
        self.data_changed.disconnect()
        self.editor.undoAvailable.disconnect()
        self.editor.redoAvailable.disconnect()
        self.editor.modificationChanged.disconnect()
        self.editor.textChanged.disconnect()
        self.editor.copyAvailable.disconnect()
        self.editor.cursorPositionChanged.disconnect()
        self.editor.setPlainText('')

    def _modification_state_changed(self):
        self.is_synced_to_container = self.is_modified
        self.modification_state_changed.emit(self.is_modified)

    def _data_changed(self):
        self.is_synced_to_container = False
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

    def _cursor_position_changed(self, *args):
        self.cursor_position_changed.emit()

    @property
    def cursor_position(self):
        c = self.editor.textCursor()
        return (c.blockNumber() + 1, c.positionInBlock())

    def cut(self):
        self.editor.cut()

    def copy(self):
        self.editor.copy()

    def go_to_line(self, line, col=None):
        self.editor.go_to_line(line, col=col)

    def paste(self):
        if not self.editor.canPaste():
            return error_dialog(self, _('No text'), _(
                'There is no suitable text in the clipboard to paste.'), show=True)
        self.editor.paste()

    def contextMenuEvent(self, ev):
        ev.ignore()

    def fix_html(self):
        if self.syntax == 'html':
            from calibre.ebooks.oeb.polish.pretty import fix_html
            self.editor.replace_text(fix_html(current_container(), unicode(self.editor.toPlainText())).decode('utf-8'))
            return True
        return False

    def pretty_print(self, name):
        from calibre.ebooks.oeb.polish.pretty import pretty_html, pretty_css, pretty_xml
        if self.syntax in {'css', 'html', 'xml'}:
            func = {'css':pretty_css, 'xml':pretty_xml}.get(self.syntax, pretty_html)
            self.editor.replace_text(func(current_container(), name, unicode(self.editor.toPlainText())).decode('utf-8'))
            return True
        return False

def launch_editor(path_to_edit, path_is_raw=False, syntax='html'):
    from calibre.gui2.tweak_book.main import option_parser
    from calibre.gui2.tweak_book.ui import Main
    opts = option_parser().parse_args([])
    app = QApplication([])
    # Create the actions that are placed into the editors toolbars
    main = Main(opts)  # noqa
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
    t = Editor(syntax)
    t.data = raw
    t.show()
    app.exec_()

