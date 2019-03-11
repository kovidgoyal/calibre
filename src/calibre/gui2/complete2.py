#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import weakref

from PyQt5.Qt import (
    QLineEdit, QAbstractListModel, Qt, pyqtSignal, QObject, QKeySequence,
    QApplication, QListView, QPoint, QModelIndex, QFont, QFontInfo,
    QStyleOptionComboBox, QStyle, QComboBox, QTimer)
try:
    from PyQt5 import sip
except ImportError:
    import sip

from calibre.constants import isosx, get_osx_version
from calibre.utils.icu import sort_key, primary_startswith, primary_contains
from calibre.gui2.widgets import EnComboBox, LineEditECM
from calibre.utils.config import tweaks
from polyglot.builtins import unicode_type


def containsq(x, prefix):
    return primary_contains(prefix, x)


class CompleteModel(QAbstractListModel):  # {{{

    def __init__(self, parent=None, sort_func=sort_key):
        QAbstractListModel.__init__(self, parent)
        self.sort_func = sort_func
        self.all_items = self.current_items = ()
        self.current_prefix = ''

    def set_items(self, items):
        items = [unicode_type(x.strip()) for x in items]
        items = [x for x in items if x]
        items = tuple(sorted(items, key=self.sort_func))
        self.beginResetModel()
        self.all_items = self.current_items = items
        self.current_prefix = ''
        self.endResetModel()

    def set_completion_prefix(self, prefix):
        old_prefix = self.current_prefix
        self.current_prefix = prefix
        if prefix == old_prefix:
            return
        if not prefix:
            self.beginResetModel()
            self.current_items = self.all_items
            self.endResetModel()
            return
        subset = prefix.startswith(old_prefix)
        universe = self.current_items if subset else self.all_items
        func = primary_startswith if tweaks['completion_mode'] == 'prefix' else containsq
        self.beginResetModel()
        self.current_items = tuple(x for x in universe if func(x, prefix))
        self.endResetModel()

    def rowCount(self, *args):
        return len(self.current_items)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            try:
                return self.current_items[index.row()]
            except IndexError:
                pass

    def index_for_prefix(self, prefix):
        for i, item in enumerate(self.current_items):
            if primary_startswith(item, prefix):
                return self.index(i)
# }}}


class Completer(QListView):  # {{{

    item_selected = pyqtSignal(object)
    relayout_needed = pyqtSignal()

    def __init__(self, completer_widget, max_visible_items=7, sort_func=sort_key):
        QListView.__init__(self)
        self.disable_popup = False
        self.completer_widget = weakref.ref(completer_widget)
        self.setWindowFlags(Qt.Popup)
        self.max_visible_items = max_visible_items
        self.setEditTriggers(self.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionBehavior(self.SelectRows)
        self.setSelectionMode(self.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setModel(CompleteModel(self, sort_func=sort_func))
        self.setMouseTracking(True)
        self.entered.connect(self.item_entered)
        self.activated.connect(self.item_chosen)
        self.pressed.connect(self.item_chosen)
        self.installEventFilter(self)

    def hide(self):
        self.setCurrentIndex(QModelIndex())
        QListView.hide(self)

    def item_chosen(self, index):
        if not self.isVisible():
            return
        self.hide()
        text = self.model().data(index, Qt.DisplayRole)
        self.item_selected.emit(unicode_type(text))

    def set_items(self, items):
        self.model().set_items(items)
        if self.isVisible():
            self.relayout_needed.emit()

    def set_completion_prefix(self, prefix):
        self.model().set_completion_prefix(prefix)
        if self.isVisible():
            self.relayout_needed.emit()

    def item_entered(self, idx):
        if self.visualRect(idx).top() < self.viewport().rect().bottom() - 5:
            # Prevent any bottom item in the list that is only partially
            # visible from triggering setCurrentIndex()
            self.entered.disconnect()
            try:
                self.setCurrentIndex(idx)
            finally:
                self.entered.connect(self.item_entered)

    def next_match(self, previous=False):
        c = self.currentIndex()
        if c.isValid():
            r = c.row()
        else:
            r = self.model().rowCount() if previous else -1
        r = r + (-1 if previous else 1)
        index = self.model().index(r % self.model().rowCount())
        self.setCurrentIndex(index)

    def scroll_to(self, orig):
        if orig:
            index = self.model().index_for_prefix(orig)
            if index is not None and index.isValid():
                self.setCurrentIndex(index)

    def popup(self, select_first=True):
        if self.disable_popup:
            return
        p = self
        m = p.model()
        widget = self.completer_widget()
        if widget is None:
            return
        screen = QApplication.desktop().availableGeometry(widget)
        h = (p.sizeHintForRow(0) * min(self.max_visible_items, m.rowCount()) + 3) + 3
        hsb = p.horizontalScrollBar()
        if hsb and hsb.isVisible():
            h += hsb.sizeHint().height()

        rh = widget.height()
        pos = widget.mapToGlobal(QPoint(0, widget.height() - 2))
        w = min(widget.width(), screen.width())

        if (pos.x() + w) > (screen.x() + screen.width()):
            pos.setX(screen.x() + screen.width() - w)
        if pos.x() < screen.x():
            pos.setX(screen.x())

        top = pos.y() - rh - screen.top() + 2
        bottom = screen.bottom() - pos.y()
        h = max(h, p.minimumHeight())
        if h > bottom:
            h = min(max(top, bottom), h)

            if top > bottom:
                pos.setY(pos.y() - h - rh + 2)

        p.setGeometry(pos.x(), pos.y(), w, h)

        if (tweaks['preselect_first_completion'] and select_first and not
                self.currentIndex().isValid() and self.model().rowCount() > 0):
            self.setCurrentIndex(self.model().index(0))

        if not p.isVisible():
            if isosx and get_osx_version() >= (10, 9, 0):
                # On mavericks the popup menu seems to use a font smaller than
                # the widgets font, see for example:
                # https://bugs.launchpad.net/bugs/1243761
                fp = QFontInfo(widget.font())
                f = QFont()
                f.setPixelSize(fp.pixelSize())
                self.setFont(f)
            p.show()

    def debug_event(self, ev):
        from calibre.gui2 import event_type_name
        print('Event:', event_type_name(ev))
        if ev.type() in (ev.KeyPress, ev.ShortcutOverride, ev.KeyRelease):
            print('\tkey:', QKeySequence(ev.key()).toString())

    def eventFilter(self, obj, e):
        'Redirect key presses from the popup to the widget'
        widget = self.completer_widget()
        if widget is None or sip.isdeleted(widget):
            return False
        etype = e.type()
        if obj is not self:
            return QObject.eventFilter(self, obj, e)

        # self.debug_event(e)

        if etype == e.KeyPress:
            try:
                key = e.key()
            except AttributeError:
                return QObject.eventFilter(self, obj, e)
            if key == Qt.Key_Escape:
                self.hide()
                e.accept()
                return True
            if key == Qt.Key_F4 and e.modifiers() & Qt.AltModifier:
                self.hide()
                e.accept()
                return True
            if key in (Qt.Key_Enter, Qt.Key_Return):
                # We handle this explicitly because on OS X activated() is
                # not emitted on pressing Enter.
                idx = self.currentIndex()
                if idx.isValid():
                    self.item_chosen(idx)
                self.hide()
                e.accept()
                return True
            if key == Qt.Key_Tab:
                idx = self.currentIndex()
                if idx.isValid():
                    self.item_chosen(idx)
                    self.hide()
                elif self.model().rowCount() > 0:
                    self.next_match()
                e.accept()
                return True
            if key in (Qt.Key_PageUp, Qt.Key_PageDown):
                # Let the list view handle these keys
                return False
            if key in (Qt.Key_Up, Qt.Key_Down):
                self.next_match(previous=key == Qt.Key_Up)
                e.accept()
                return True
            # Send to widget
            widget.eat_focus_out = False
            widget.keyPressEvent(e)
            widget.eat_focus_out = True
            if not widget.hasFocus():
                # Widget lost focus hide the popup
                self.hide()
            if e.isAccepted():
                return True
        elif isosx and etype == e.InputMethodQuery and e.queries() == (Qt.ImHints | Qt.ImEnabled) and self.isVisible():
            # In Qt 5 the Esc key causes this event and the line edit does not
            # handle it, which causes the parent dialog to be closed
            # See https://bugreports.qt-project.org/browse/QTBUG-41806
            e.accept()
            return True
        elif etype == e.MouseButtonPress and hasattr(e, 'globalPos') and not self.rect().contains(self.mapFromGlobal(e.globalPos())):
            # A click outside the popup, close it
            if isinstance(widget, QComboBox):
                # This workaround is needed to ensure clicking on the drop down
                # arrow of the combobox closes the popup
                opt = QStyleOptionComboBox()
                widget.initStyleOption(opt)
                sc = widget.style().hitTestComplexControl(QStyle.CC_ComboBox, opt, widget.mapFromGlobal(e.globalPos()), widget)
                if sc == QStyle.SC_ComboBoxArrow:
                    QTimer.singleShot(0, self.hide)
                    e.accept()
                    return True
            self.hide()
            e.accept()
            return True
        elif etype in (e.InputMethod, e.ShortcutOverride):
            QApplication.sendEvent(widget, e)
        return False
# }}}


class LineEdit(QLineEdit, LineEditECM):
    '''
    A line edit that completes on multiple items separated by a
    separator. Use the :meth:`update_items_cache` to set the list of
    all possible completions. Separator can be controlled with the
    :meth:`set_separator` and :meth:`set_space_before_sep` methods.

    A call to self.set_separator(None) will allow this widget to be used
    to complete non multiple fields as well.
    '''
    item_selected = pyqtSignal(object)

    def __init__(self, parent=None, completer_widget=None, sort_func=sort_key):
        QLineEdit.__init__(self, parent)

        self.sep = ','
        self.space_before_sep = False
        self.add_separator = True
        self.original_cursor_pos = None
        completer_widget = (self if completer_widget is None else
                completer_widget)

        self.mcompleter = Completer(completer_widget, sort_func=sort_func)
        self.mcompleter.item_selected.connect(self.completion_selected,
                type=Qt.QueuedConnection)
        self.mcompleter.relayout_needed.connect(self.relayout)
        self.mcompleter.setFocusProxy(completer_widget)
        self.textEdited.connect(self.text_edited)
        self.no_popup = False

    # Interface {{{
    def update_items_cache(self, complete_items):
        self.all_items = complete_items

    def set_separator(self, sep):
        self.sep = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    def set_add_separator(self, what):
        self.add_separator = bool(what)

    @dynamic_property
    def all_items(self):
        def fget(self):
            return self.mcompleter.model().all_items

        def fset(self, items):
            self.mcompleter.model().set_items(items)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def disable_popup(self):
        def fget(self):
            return self.mcompleter.disable_popup

        def fset(self, val):
            self.mcompleter.disable_popup = bool(val)
        return property(fget=fget, fset=fset)
    # }}}

    def event(self, ev):
        # See https://bugreports.qt.io/browse/QTBUG-46911
        try:
            if ev.type() == ev.ShortcutOverride and (
                    ev.key() in (Qt.Key_Left, Qt.Key_Right) and (ev.modifiers() & ~Qt.KeypadModifier) == Qt.ControlModifier):
                ev.accept()
        except AttributeError:
            pass
        return QLineEdit.event(self, ev)

    def complete(self, show_all=False, select_first=True):
        orig = None
        if show_all:
            orig = self.mcompleter.model().current_prefix
            self.mcompleter.set_completion_prefix('')
        if not self.mcompleter.model().current_items:
            self.mcompleter.hide()
            return
        self.mcompleter.popup(select_first=select_first)
        self.setFocus(Qt.OtherFocusReason)
        self.mcompleter.scroll_to(orig)

    def relayout(self):
        self.mcompleter.popup()
        self.setFocus(Qt.OtherFocusReason)

    def text_edited(self, *args):
        if self.no_popup:
            return
        self.update_completions()
        select_first = len(self.mcompleter.model().current_prefix) > 0
        if not select_first:
            self.mcompleter.setCurrentIndex(QModelIndex())
        self.complete(select_first=select_first)

    def update_completions(self):
        ' Update the list of completions '
        self.original_cursor_pos = cpos = self.cursorPosition()
        text = unicode_type(self.text())
        prefix = text[:cpos]
        complete_prefix = prefix.lstrip()
        if self.sep:
            complete_prefix = prefix.split(self.sep)[-1].lstrip()
        self.mcompleter.set_completion_prefix(complete_prefix)

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
            curtext = unicode_type(self.text())
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
        before_text, after_text = self.get_completed_text(unicode_type(text))
        self.setText(before_text + after_text)
        self.setCursorPosition(len(before_text))
        self.item_selected.emit(text)


class EditWithComplete(EnComboBox):

    item_selected = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        EnComboBox.__init__(self, *args)
        self.setLineEdit(LineEdit(self, completer_widget=self, sort_func=kwargs.get('sort_func', sort_key)))
        self.lineEdit().item_selected.connect(self.item_selected)
        self.setCompleter(None)
        self.eat_focus_out = True
        self.installEventFilter(self)

    # Interface {{{
    def showPopup(self):
        orig = self.disable_popup
        self.disable_popup = False
        try:
            self.lineEdit().complete(show_all=True)
        finally:
            self.disable_popup = orig

    def update_items_cache(self, complete_items):
        self.lineEdit().update_items_cache(complete_items)

    def set_separator(self, sep):
        self.lineEdit().set_separator(sep)

    def set_space_before_sep(self, space_before):
        self.lineEdit().set_space_before_sep(space_before)

    def set_add_separator(self, what):
        self.lineEdit().set_add_separator(what)

    def show_initial_value(self, what):
        what = unicode_type(what) if what else u''
        self.setText(what)
        self.lineEdit().selectAll()

    @dynamic_property
    def all_items(self):
        def fget(self):
            return self.lineEdit().all_items

        def fset(self, val):
            self.lineEdit().all_items = val
        return property(fget=fget, fset=fset)

    @dynamic_property
    def disable_popup(self):
        def fget(self):
            return self.lineEdit().disable_popup

        def fset(self, val):
            self.lineEdit().disable_popup = bool(val)
        return property(fget=fget, fset=fset)
    # }}}

    def text(self):
        return unicode_type(self.lineEdit().text())

    def selectAll(self):
        self.lineEdit().selectAll()

    def setText(self, val):
        le = self.lineEdit()
        le.no_popup = True
        le.setText(val)
        le.no_popup = False

    def setCursorPosition(self, *args):
        self.lineEdit().setCursorPosition(*args)

    @property
    def textChanged(self):
        return self.lineEdit().textChanged

    def clear(self):
        self.lineEdit().clear()
        EnComboBox.clear(self)

    def eventFilter(self, obj, e):
        try:
            c = self.lineEdit().mcompleter
        except AttributeError:
            return False
        etype = e.type()
        if self.eat_focus_out and self is obj and etype == e.FocusOut:
            if c.isVisible():
                return True
        return EnComboBox.eventFilter(self, obj, e)


if __name__ == '__main__':
    from PyQt5.Qt import QDialog, QVBoxLayout
    app = QApplication([])
    d = QDialog()
    d.setLayout(QVBoxLayout())
    le = EditWithComplete(d)
    d.layout().addWidget(le)
    items = ['one', 'otwo', 'othree', 'ooone', 'ootwo',
        'oothree', 'a1', 'a2',u'Edgas', u'Èdgar', u'Édgaq', u'Edgar', u'Édgar']
    le.update_items_cache(items)
    le.show_initial_value('')
    d.exec_()
