#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QLineEdit, QListView, QAbstractListModel, Qt, \
        QApplication, QPoint, QItemDelegate, QStyleOptionViewItem, \
        QStyle, QEvent, pyqtSignal

from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key, lower
from calibre.gui2 import NONE
from calibre.gui2.widgets import EnComboBox

class CompleterItemDelegate(QItemDelegate): # {{{

    ''' Renders the current item as thought it were selected '''

    def __init__(self, view):
        self.view = view
        QItemDelegate.__init__(self, view)

    def paint(self, p, opt, idx):
        opt = QStyleOptionViewItem(opt)
        opt.showDecorationSelected = True
        if self.view.currentIndex() == idx:
            opt.state |= QStyle.State_HasFocus
        QItemDelegate.paint(self, p, opt, idx)

# }}}

class CompleteWindow(QListView): # {{{

    '''
    The completion popup. For keyboard and mouse handling see
    :meth:`eventFilter`.
    '''

    #: This signal is emitted when the user selects one of the listed
    #: completions, by mouse or keyboard
    completion_selected = pyqtSignal(object)

    def __init__(self, widget, model):
        self.widget = widget
        QListView.__init__(self)
        self.setVisible(False)
        self.setParent(None, Qt.Popup)
        self.setAlternatingRowColors(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._d = CompleterItemDelegate(self)
        self.setItemDelegate(self._d)
        self.setModel(model)
        self.setFocusProxy(widget)
        self.installEventFilter(self)
        self.clicked.connect(self.do_selected)
        self.entered.connect(self.do_entered)
        self.setMouseTracking(True)

    def do_entered(self, idx):
        if idx.isValid():
            self.setCurrentIndex(idx)

    def do_selected(self, idx=None):
        idx = self.currentIndex() if idx is None else idx
        if idx.isValid():
            data = unicode(self.model().data(idx, Qt.DisplayRole))
            self.completion_selected.emit(data)
        self.hide()

    def eventFilter(self, o, e):
        if o is not self:
            return False
        if e.type() == e.KeyPress:
            key = e.key()
            if key in (Qt.Key_Escape, Qt.Key_Backtab) or \
                    (key == Qt.Key_F4 and (e.modifiers() & Qt.AltModifier)):
                self.hide()
                return True
            elif key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                if key == Qt.Key_Tab and not self.currentIndex().isValid():
                    if self.model().rowCount() > 0:
                        self.setCurrentIndex(self.model().index(0))
                self.do_selected()
                return True
            elif key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp,
                    Qt.Key_PageDown):
                return False
            # Send key event to associated line edit
            self.widget.eat_focus_out = False
            try:
                self.widget.event(e)
            finally:
                self.widget.eat_focus_out = True
            if not self.widget.hasFocus():
                # Line edit lost focus
                self.hide()
            if e.isAccepted():
                # Line edit consumed event
                return True
        elif e.type() == e.MouseButtonPress:
            # Hide popup if user clicks outside it, otherwise
            # pass event to popup
            if not self.underMouse():
                self.hide()
                return True
        elif e.type() in (e.InputMethod, e.ShortcutOverride):
            QApplication.sendEvent(self.widget, e)

        return False # Do not filter this event

# }}}

class CompleteModel(QAbstractListModel):

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.sep = ','
        self.space_before_sep = False
        self.items = []
        self.lowered_items = []
        self.matches = []

    def set_items(self, items):
        items = [unicode(x.strip()) for x in items]
        self.items = list(sorted(items, key=lambda x: sort_key(x)))
        self.lowered_items = [lower(x) for x in self.items]
        self.matches = []
        self.reset()

    def rowCount(self, *args):
        return len(self.matches)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            r = index.row()
            try:
                return self.matches[r]
            except IndexError:
                pass
        return NONE

    def get_matches(self, prefix):
        '''
        Return all matches that (case insensitively) start with prefix
        '''
        prefix = lower(prefix)
        ans = []
        if prefix:
            for i, test in enumerate(self.lowered_items):
                if test.startswith(prefix):
                    ans.append(self.items[i])
        return ans

    def update_matches(self, matches):
        self.matches = matches
        self.reset()

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
        self.eat_focus_out = True
        self.max_visible_items = 7
        self.current_prefix = None
        QLineEdit.__init__(self, parent)

        self._model = CompleteModel(parent=self)
        self.complete_window = CompleteWindow(self, self._model)
        self.textEdited.connect(self.text_edited)
        self.complete_window.completion_selected.connect(self.completion_selected)
        self.installEventFilter(self)

    # Interface {{{
    def update_items_cache(self, complete_items):
        self.all_items = complete_items

    def set_separator(self, sep):
        self.sep = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    # }}}

    def eventFilter(self, o, e):
        if self.eat_focus_out and o is self and e.type() == QEvent.FocusOut:
            if self.complete_window.isVisible():
                return True # Filter this event since the cw is visible
        return QLineEdit.eventFilter(self, o, e)

    def hide_completion_window(self):
        self.complete_window.hide()


    def text_edited(self, *args):
        self.update_completions()

    def update_completions(self):
        ' Update the list of completions '
        if not self.complete_window.isVisible() and not self.hasFocus():
            return
        cpos = self.cursorPosition()
        text = unicode(self.text())
        prefix = text[:cpos]
        self.current_prefix = prefix
        complete_prefix = prefix.lstrip()
        if self.sep:
            complete_prefix = prefix = prefix.split(self.sep)[-1].lstrip()

        matches = self._model.get_matches(complete_prefix)
        self.update_complete_window(matches)

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
        prefix_len, ctext = self.get_completed_text(text)
        if self.sep is None:
            self.setText(ctext)
            self.setCursorPosition(len(ctext))
        else:
            cursor_pos = self.cursorPosition()
            self.setText(ctext)
            self.setCursorPosition(cursor_pos - prefix_len + len(text))

    def update_complete_window(self, matches):
        self._model.update_matches(matches)
        if matches:
            self.show_complete_window()
        else:
            self.complete_window.hide()


    def position_complete_window(self):
        popup = self.complete_window
        screen = QApplication.desktop().availableGeometry(self)
        h = (popup.sizeHintForRow(0) * min(self.max_visible_items,
            popup.model().rowCount()) + 3) + 3
        hsb = popup.horizontalScrollBar()
        if hsb and hsb.isVisible():
            h += hsb.sizeHint().height()

        rh = self.height()
        pos = self.mapToGlobal(QPoint(0, self.height() - 2))
        w = self.width()

        if w > screen.width():
            w = screen.width()
        if (pos.x() + w) > (screen.x() + screen.width()):
            pos.setX(screen.x() + screen.width() - w)
        if (pos.x() < screen.x()):
            pos.setX(screen.x())

        top = pos.y() - rh - screen.top() + 2
        bottom = screen.bottom() - pos.y()
        h = max(h, popup.minimumHeight())
        if h > bottom:
            h = min(max(top, bottom), h)
            if top > bottom:
                pos.setY(pos.y() - h - rh + 2)

        popup.setGeometry(pos.x(), pos.y(), w, h)


    def show_complete_window(self):
        self.position_complete_window()
        self.complete_window.show()

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
