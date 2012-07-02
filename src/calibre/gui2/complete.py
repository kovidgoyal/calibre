#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (QLineEdit, QAbstractListModel, Qt,
        QApplication, QCompleter)

from calibre.utils.icu import sort_key, lower
from calibre.gui2 import NONE
from calibre.gui2.widgets import EnComboBox, LineEditECM
from calibre.utils.config_base import tweaks

class CompleteModel(QAbstractListModel):

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.items = []
        self.sorting = QCompleter.UnsortedModel

    def set_items(self, items):
        items = [unicode(x.strip()) for x in items]
        if len(items) < tweaks['completion_change_to_ascii_sorting']:
            self.items = sorted(items, key=lambda x: sort_key(x))
            self.sorting = QCompleter.UnsortedModel
        else:
            self.items = sorted(items, key=lambda x:x.lower())
            self.sorting = QCompleter.CaseInsensitivelySortedModel
        self.lowered_items = [lower(x) for x in self.items]
        self.reset()

    def rowCount(self, *args):
        return len(self.items)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            r = index.row()
            try:
                return self.items[r]
            except IndexError:
                pass
        return NONE


class MultiCompleteLineEdit(QLineEdit, LineEditECM):
    '''
    A line edit that completes on multiple items separated by a
    separator. Use the :meth:`update_items_cache` to set the list of
    all possible completions. Separator can be controlled with the
    :meth:`set_separator` and :meth:`set_space_before_sep` methods.

    A call to self.set_separator(None) will allow this widget to be used
    to complete non multiple fields as well.
    '''

    def __init__(self, parent=None, completer_widget=None):
        QLineEdit.__init__(self, parent)

        self.sep = ','
        self.space_before_sep = False
        self.add_separator = True
        self.original_cursor_pos = None

        self._model = CompleteModel(parent=self)
        self._completer = c = QCompleter(self._model, self)
        c.setWidget(self if completer_widget is None else completer_widget)
        c.setCompletionMode(QCompleter.PopupCompletion)
        c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setModelSorting(self._model.sorting)
        c.setCompletionRole(Qt.DisplayRole)
        p = c.popup()
        p.setMouseTracking(True)
        p.entered.connect(self.item_entered)
        c.popup().setAlternatingRowColors(True)

        c.activated.connect(self.completion_selected,
                type=Qt.QueuedConnection)
        self.textEdited.connect(self.text_edited)

    # Interface {{{
    def update_items_cache(self, complete_items):
        self.all_items = complete_items

    def set_separator(self, sep):
        self.sep = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    def set_add_separator(self, what):
        self.add_separator = bool(what)

    # }}}

    def item_entered(self, idx):
        self._completer.popup().setCurrentIndex(idx)

    def text_edited(self, *args):
        self.update_completions()
        self._completer.complete()

    def update_completions(self):
        ' Update the list of completions '
        self.original_cursor_pos = cpos = self.cursorPosition()
        text = unicode(self.text())
        prefix = text[:cpos]
        self.current_prefix = prefix
        complete_prefix = prefix.lstrip()
        if self.sep:
            complete_prefix = prefix.split(self.sep)[-1].lstrip()
        self._completer.setCompletionPrefix(complete_prefix)

    def get_completed_text(self, text):
        'Get completed text in before and after parts'
        if self.sep is None:
            return text, ''
        else:
            cursor_pos = self.original_cursor_pos
            if cursor_pos is None:
                cursor_pos = self.cursorPosition()
            self.original_cursor_pos = None
            # Split text
            curtext = unicode(self.text())
            before_text = curtext[:cursor_pos]
            after_text = curtext[cursor_pos:].rstrip()
            # Remove the completion prefix from the before text
            before_text = self.sep.join(before_text.split(self.sep)[:-1]).rstrip()
            if before_text:
                # Add the separator to the end of before_text
                if self.space_before_sep:
                    before_text += ' '
                before_text += self.sep + ' '
            if self.add_separator or after_text:
                # Add separator to the end of completed text
                if self.space_before_sep:
                    text = text.rstrip() + ' '
                completed_text = text + self.sep + ' '
            else:
                completed_text = text
            return before_text + completed_text, after_text

    def completion_selected(self, text):
        before_text, after_text = self.get_completed_text(unicode(text))
        self.setText(before_text + after_text)
        self.setCursorPosition(len(before_text))

    @dynamic_property
    def all_items(self):
        def fget(self):
            return self._model.items
        def fset(self, items):
            self._model.set_items(items)
            self._completer.setModelSorting(self._model.sorting)
        return property(fget=fget, fset=fset)

class MultiCompleteComboBox(EnComboBox):

    def __init__(self, *args):
        EnComboBox.__init__(self, *args)
        self.le = MultiCompleteLineEdit(self, completer_widget=self)
        self.setLineEdit(self.le)

    def showPopup(self):
        c = self.le._completer
        v = unicode(c.currentCompletion())
        c.setCompletionPrefix('')
        c.complete()
        if c.model().rowCount() < tweaks['completion_change_to_ascii_sorting']:
            i = 0;
            while c.setCurrentRow(i):
                cr = unicode(c.currentIndex().data().toString())
                if cr.startswith(v):
                    c.popup().setCurrentIndex(c.currentIndex())
                    break
                i += 1

    def update_items_cache(self, complete_items):
        self.lineEdit().update_items_cache(complete_items)

    def set_separator(self, sep):
        self.lineEdit().set_separator(sep)

    def set_space_before_sep(self, space_before):
        self.lineEdit().set_space_before_sep(space_before)

    def set_add_separator(self, what):
        self.lineEdit().set_add_separator(what)

    def show_initial_value(self, what):
        what = unicode(what) if what else u''
        le = self.lineEdit()
        self.setEditText(what)
        le.selectAll()

if __name__ == '__main__':
    from PyQt4.Qt import QDialog, QVBoxLayout
    app = QApplication([])
    d = QDialog()
    d.setLayout(QVBoxLayout())
    le = MultiCompleteComboBox(d)
    d.layout().addWidget(le)
    items = ['one', 'otwo', 'othree', 'ooone', 'ootwo',
        'oothree']
    le.update_items_cache(items)
    le.show_initial_value('')
    d.exec_()
