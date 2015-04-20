#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QPushButton, QPixmap, QIcon, QColor, Qt, QColorDialog, pyqtSignal,
    QKeySequence, QToolButton, QDialog, QDialogButtonBox)

from calibre.gui2 import gprefs
from calibre.gui2.complete2 import LineEdit, EditWithComplete
from calibre.gui2.widgets import history

class HistoryMixin(object):

    max_history_items = None

    def __init__(self, *args, **kwargs):
        pass

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.history = history.get(self.store_name, [])
        self.set_separator(None)
        self.update_items_cache(self.history)
        self.setText('')
        try:
            self.editingFinished.connect(self.save_history)
        except AttributeError:
            self.lineEdit().editingFinished.connect(self.save_history)

    def save_history(self):
        ct = unicode(self.text())
        if len(ct) > 2:
            try:
                self.history.remove(ct)
            except ValueError:
                pass
            self.history.insert(0, ct)
            if self.max_history_items is not None:
                del self.history[self.max_history_items:]
            history.set(self.store_name, self.history)
            self.update_items_cache(self.history)

    def clear_history(self):
        self.history = []
        history.set(self.store_name, self.history)
        self.update_items_cache(self.history)

class HistoryLineEdit2(LineEdit, HistoryMixin):

    def __init__(self, parent=None, completer_widget=None, sort_func=lambda x:None):
        LineEdit.__init__(self, parent=parent, completer_widget=completer_widget, sort_func=sort_func)

class HistoryComboBox(EditWithComplete, HistoryMixin):

    def __init__(self, parent=None):
        EditWithComplete.__init__(self, parent, sort_func=lambda x:None)

class ColorButton(QPushButton):

    color_changed = pyqtSignal(object)

    def __init__(self, initial_color=None, parent=None, choose_text=None):
        QPushButton.__init__(self, parent)
        self._color = None
        self.choose_text = choose_text or _('Choose &color')
        self.color = initial_color
        self.clicked.connect(self.choose_color)

    @dynamic_property
    def color(self):
        def fget(self):
            return self._color
        def fset(self, val):
            val = unicode(val or '')
            col = QColor(val)
            orig = self._color
            if col.isValid():
                self._color = val
                self.setText(val)
                p = QPixmap(self.iconSize())
                p.fill(col)
                self.setIcon(QIcon(p))
            else:
                self._color = None
                self.setText(self.choose_text)
                self.setIcon(QIcon())
            if orig != col:
                self.color_changed.emit(self._color)
        return property(fget=fget, fset=fset)

    def choose_color(self):
        col = QColorDialog.getColor(QColor(self._color or Qt.white), self, _('Choose a color'))
        if col.isValid():
            self.color = unicode(col.name())


def access_key(k):
    'Return shortcut text suitable for adding to a menu item'
    if QKeySequence.keyBindings(k):
        return '\t' + QKeySequence(k).toString(QKeySequence.NativeText)
    return ''

def populate_standard_spinbox_context_menu(spinbox, menu, add_clear=False):
    m = menu
    le = spinbox.lineEdit()
    m.addAction(_('Cu&t') + access_key(QKeySequence.Cut), le.cut).setEnabled(not le.isReadOnly() and le.hasSelectedText())
    m.addAction(_('&Copy') + access_key(QKeySequence.Copy), le.copy).setEnabled(le.hasSelectedText())
    m.addAction(_('&Paste') + access_key(QKeySequence.Paste), le.paste).setEnabled(not le.isReadOnly())
    m.addAction(_('Delete') + access_key(QKeySequence.Delete), le.del_).setEnabled(not le.isReadOnly() and le.hasSelectedText())
    m.addSeparator()
    m.addAction(_('Select &All') + access_key(QKeySequence.SelectAll), spinbox.selectAll)
    m.addSeparator()
    m.addAction(_('&Step up'), spinbox.stepUp)
    m.addAction(_('Step &down'), spinbox.stepDown)
    m.setAttribute(Qt.WA_DeleteOnClose)

class RightClickButton(QToolButton):

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton and self.menu() is not None:
            self.showMenu()
            ev.accept()
            return
        return QToolButton.mousePressEvent(self, ev)

class Dialog(QDialog):

    '''
    An improved version of Qt's QDialog class. This automatically remembers the
    last used size, automatically connects the signals for QDialogButtonBox,
    automatically sets the window title and if the dialog has an object names
    splitter, automatically saves the splitter state.

    In order to use it, simply subclass an implement setup_ui(). You can also
    implement sizeHint() to give the dialog a different default size when shown
    for the first time.
    '''

    def __init__(self, title, name, parent=None, prefs=gprefs):
        QDialog.__init__(self, parent)
        self.prefs_for_persistence = prefs
        self.setWindowTitle(title)
        self.name = name
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)

        self.setup_ui()

        self.resize(self.sizeHint())
        geom = self.prefs_for_persistence.get(name + '-geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        if hasattr(self, 'splitter'):
            state = self.prefs_for_persistence.get(name + '-splitter-state', None)
            if state is not None:
                self.splitter.restoreState(state)

    def accept(self):
        self.prefs_for_persistence.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            self.prefs_for_persistence.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.accept(self)

    def reject(self):
        self.prefs_for_persistence.set(self.name + '-geometry', bytearray(self.saveGeometry()))
        if hasattr(self, 'splitter'):
            self.prefs_for_persistence.set(self.name + '-splitter-state', bytearray(self.splitter.saveState()))
        QDialog.reject(self)

    def setup_ui(self):
        raise NotImplementedError('You must implement this method in Dialog subclasses')

