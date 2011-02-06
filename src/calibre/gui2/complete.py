#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QLineEdit, QAbstractListModel, Qt, \
        QApplication, QCompleter

from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key, lower
from calibre.gui2 import NONE
from calibre.gui2.widgets import EnComboBox

class CompleteModel(QAbstractListModel):

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.sep = ','
        self.space_before_sep = False
        self.items = []

    def set_items(self, items):
        items = [unicode(x.strip()) for x in items]
        self.items = list(sorted(items, key=lambda x: sort_key(x)))
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


class MultiCompleteLineEdit(QLineEdit):
    '''
    A line edit that completes on multiple items separated by a
    separator. Use the :meth:`update_items_cache` to set the list of
    all possible completions. Separator can be controlled with the
    :meth:`set_separator` and :meth:`set_space_before_sep` methods.

    A call to self.set_separator(None) will allow this widget to be used
    to complete non multiple fields as well.
    '''

    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        self._model = CompleteModel(parent=self)
        self._completer = c = QCompleter(self._model, self)
        c.setWidget(self)
        c.setCompletionMode(QCompleter.PopupCompletion)
        c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setModelSorting(QCompleter.CaseInsensitivelySortedModel)
        c.setCompletionRole(Qt.DisplayRole)
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

    # }}}

    def text_edited(self, *args):
        self.update_completions()
        self._completer.complete()

    def update_completions(self):
        ' Update the list of completions '
        cpos = self.cursorPosition()
        text = unicode(self.text())
        prefix = text[:cpos]
        self.current_prefix = prefix
        complete_prefix = prefix.lstrip()
        if self.sep:
            complete_prefix = prefix.split(self.sep)[-1].lstrip()
        self._completer.setCompletionPrefix(complete_prefix)

    def get_completed_text(self, text):
        '''
        Get completed text from current cursor position and the completion
        text
        '''
        if self.sep is None:
            return -1, text
        else:
            cursor_pos = self.cursorPosition()
            before_text = unicode(self.text())[:cursor_pos]
            after_text = unicode(self.text())[cursor_pos:]
            prefix_len = len(before_text.split(self.sep)[-1].lstrip())
            if tweaks['completer_append_separator']:
                prefix_len = len(before_text.split(self.sep)[-1].lstrip())
                completed_text = before_text[:cursor_pos - prefix_len] + text + self.sep + ' ' + after_text
                prefix_len = prefix_len - len(self.sep) - 1
                if prefix_len < 0:
                    prefix_len = 0
            else:
                prefix_len = len(before_text.split(self.sep)[-1].lstrip())
                completed_text = before_text[:cursor_pos - prefix_len] + text + after_text
            return prefix_len, completed_text


    def completion_selected(self, text):
        prefix_len, ctext = self.get_completed_text(unicode(text))
        if self.sep is None:
            self.setText(ctext)
            self.setCursorPosition(len(ctext))
        else:
            cursor_pos = self.cursorPosition()
            self.setText(ctext)
            self.setCursorPosition(cursor_pos - prefix_len + len(text))

    @dynamic_property
    def all_items(self):
        def fget(self):
            return self._model.items
        def fset(self, items):
            self._model.set_items(items)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def sep(self):
        def fget(self):
            return self._model.sep
        def fset(self, val):
            self._model.sep = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def space_before_sep(self):
        def fget(self):
            return self._model.space_before_sep
        def fset(self, val):
            self._model.space_before_sep = val
        return property(fget=fget, fset=fset)

class MultiCompleteComboBox(EnComboBox):

    def __init__(self, *args):
        EnComboBox.__init__(self, *args)
        self.setLineEdit(MultiCompleteLineEdit(self))
        # Needed to allow changing the case of an existing item
        # otherwise on focus out, the text is changed to the
        # item that matches case insensitively
        c = self.lineEdit().completer()
        c.setCaseSensitivity(Qt.CaseSensitive)

    def update_items_cache(self, complete_items):
        self.lineEdit().update_items_cache(complete_items)

    def set_separator(self, sep):
        self.lineEdit().set_separator(sep)

    def set_space_before_sep(self, space_before):
        self.lineEdit().set_space_before_sep(space_before)



if __name__ == '__main__':
    from PyQt4.Qt import QDialog, QVBoxLayout
    app = QApplication([])
    d = QDialog()
    d.setLayout(QVBoxLayout())
    le = MultiCompleteLineEdit(d)
    d.layout().addWidget(le)
    le.all_items = ['one', 'otwo', 'othree', 'ooone', 'ootwo', 'oothree']
    d.exec_()
