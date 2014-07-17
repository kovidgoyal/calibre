#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QPushButton, QPixmap, QIcon, QColor, Qt, QColorDialog, pyqtSignal

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

