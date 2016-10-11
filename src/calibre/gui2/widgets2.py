#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import weakref

from PyQt5.Qt import (
    QPushButton, QPixmap, QIcon, QColor, Qt, QColorDialog, pyqtSignal,
    QKeySequence, QToolButton, QDialog, QDialogButtonBox, QComboBox, QFont,
    QAbstractListModel, QModelIndex, QApplication, QStyledItemDelegate,
    QUndoCommand, QUndoStack)

from calibre.ebooks.metadata import rating_to_stars
from calibre.gui2 import gprefs, rating_font
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
    automatically sets the window title and if the dialog has an object named
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


class RatingModel(QAbstractListModel):

    def __init__(self, parent=None, is_half_star=False):
        QAbstractListModel.__init__(self, parent)
        self.is_half_star = is_half_star
        self.rating_font = QFont(rating_font())
        self.null_text = _('Not rated')

    def rowCount(self, parent=QModelIndex()):
        return 11 if self.is_half_star else 6

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            val = index.row() * (1 if self.is_half_star else 2)
            return rating_to_stars(val, self.is_half_star) or self.null_text
        if role == Qt.FontRole:
            return QApplication.instance().font() if index.row() == 0 else self.rating_font


class UndoCommand(QUndoCommand):

    def __init__(self, widget, val):
        QUndoCommand.__init__(self)
        self.widget = weakref.ref(widget)
        self.undo_val = widget.rating_value
        self.redo_val = val

        def undo(self):
            w = self.widget()
            w.setCurrentIndex(self.undo_val)

        def redo(self):
            w = self.widget()
            w.setCurrentIndex(self.redo_val)


class RatingEditor(QComboBox):

    def __init__(self, parent=None, is_half_star=False):
        QComboBox.__init__(self, parent)
        self.undo_stack = QUndoStack(self)
        self.undo, self.redo = self.undo_stack.undo, self.undo_stack.redo
        self.allow_undo = False
        self.is_half_star = is_half_star
        self._model = RatingModel(is_half_star=is_half_star, parent=self)
        self.setModel(self._model)
        self.delegate = QStyledItemDelegate(self)
        self.view().setItemDelegate(self.delegate)
        self.view().setStyleSheet('QListView { background: palette(window) }\nQListView::item { padding: 6px }')
        self.setMaxVisibleItems(self.count())
        self.currentIndexChanged.connect(self.update_font)

    @property
    def null_text(self):
        return self._model.null_text

    @null_text.setter
    def null_text(self, val):
        self._model.null_text = val
        self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(0, 0))

    def update_font(self):
        if self.currentIndex() == 0:
            self.setFont(QApplication.instance().font())
        else:
            self.setFont(self._model.rating_font)

    def clear_to_undefined(self):
        self.setCurrentIndex(0)

    @property
    def rating_value(self):
        ' An integer from 0 to 10 '
        ans = self.currentIndex()
        if not self.is_half_star:
            ans *= 2
        return ans

    @rating_value.setter
    def rating_value(self, val):
        val = max(0, min(int(val or 0), 10))
        if self.allow_undo:
            cmd = UndoCommand(self, val)
            self.undo_stack.push(cmd)
        else:
            self.undo_stack.clear()
        if not self.is_half_star:
            val //= 2
        self.setCurrentIndex(val)

    def keyPressEvent(self, ev):
        if ev == QKeySequence.Undo:
            self.undo()
            return ev.accept()
        if ev == QKeySequence.Redo:
            self.redo()
            return ev.accept()
        k = ev.key()
        num = {getattr(Qt, 'Key_%d'%i):i for i in range(6)}.get(k)
        if num is None:
            return QComboBox.keyPressEvent(self, ev)
        ev.accept()
        if self.is_half_star:
            num *= 2
        self.setCurrentIndex(num)

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    app.load_builtin_fonts()
    q = RatingEditor(is_half_star=True)
    q.rating_value = 7
    q.show()
    app.exec_()
