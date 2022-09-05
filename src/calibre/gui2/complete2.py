#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QLineEdit, QAbstractListModel, Qt, pyqtSignal, QObject, QKeySequence, QAbstractItemView,
    QApplication, QListView, QPoint, QModelIndex, QEvent,
    QStyleOptionComboBox, QStyle, QComboBox, QTimer, sip)

from calibre.constants import ismacos
from calibre.utils.icu import sort_key, primary_startswith, primary_contains
from calibre.gui2.widgets import EnComboBox, LineEditECM
from calibre.utils.config import tweaks


def containsq(x, prefix):
    return primary_contains(prefix, x)


class CompleteModel(QAbstractListModel):  # {{{

    def __init__(self, parent=None, sort_func=sort_key, strip_completion_entries=True):
        QAbstractListModel.__init__(self, parent)
        self.strip_completion_entries = strip_completion_entries
        self.sort_func = sort_func
        self.all_items = self.current_items = ()
        self.current_prefix = ''

    def set_items(self, items):
        if self.strip_completion_entries:
            items = (str(x).strip() for x in items if x)
        else:
            items = (str(x) for x in items if x)
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
        if role == Qt.ItemDataRole.DisplayRole:
            try:
                return self.current_items[index.row()].replace('\n', ' ')
            except IndexError:
                pass
        if role == Qt.ItemDataRole.UserRole:
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
    apply_current_text = pyqtSignal()
    relayout_needed = pyqtSignal()

    def __init__(self, completer_widget, max_visible_items=7, sort_func=sort_key, strip_completion_entries=True):
        QListView.__init__(self, completer_widget)
        self.disable_popup = False
        self.setWindowFlags(Qt.WindowType.Popup)
        self.max_visible_items = max_visible_items
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setAlternatingRowColors(True)
        self.setModel(CompleteModel(self, sort_func=sort_func, strip_completion_entries=strip_completion_entries))
        self.setMouseTracking(True)
        self.activated.connect(self.item_chosen)
        self.pressed.connect(self.item_chosen)
        self.installEventFilter(self)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tab_accepts_uncompleted_text = (tweaks['tab_accepts_uncompleted_text'] and
                                             not tweaks['preselect_first_completion'])

    def hide(self):
        self.setCurrentIndex(QModelIndex())
        QListView.hide(self)

    def item_chosen(self, index):
        if not self.isVisible():
            return
        self.hide()
        text = self.model().data(index, Qt.ItemDataRole.UserRole)
        self.item_selected.emit(str(text))

    def set_items(self, items):
        self.model().set_items(items)
        if self.isVisible():
            self.relayout_needed.emit()

    def set_completion_prefix(self, prefix):
        self.model().set_completion_prefix(prefix)
        if self.isVisible():
            self.relayout_needed.emit()

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
        widget = self.parent()
        if widget is None:
            return
        screen = widget.screen().availableGeometry()
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
            p.show()

    def debug_event(self, ev):
        from calibre.gui2 import event_type_name
        print('Event:', event_type_name(ev))
        if ev.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride, QEvent.Type.KeyRelease):
            print('\tkey:', QKeySequence(ev.key()).toString())

    def mouseMoveEvent(self, ev):
        idx = self.indexAt(ev.pos())
        if idx.isValid():
            ci = self.currentIndex()
            if idx.row() != ci.row():
                self.setCurrentIndex(idx)
        return QListView.mouseMoveEvent(self, ev)

    def eventFilter(self, obj, e):
        'Redirect key presses from the popup to the widget'
        widget = self.parent()
        if widget is None or sip.isdeleted(widget):
            return False
        etype = e.type()
        if obj is not self:
            return QObject.eventFilter(self, obj, e)

        # self.debug_event(e)

        if etype == QEvent.Type.KeyPress:
            try:
                key = e.key()
            except AttributeError:
                return QObject.eventFilter(self, obj, e)
            if key == Qt.Key.Key_Escape:
                self.hide()
                e.accept()
                return True
            if key == Qt.Key.Key_F4 and e.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.hide()
                e.accept()
                return True
            if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                # We handle this explicitly because on OS X activated() is
                # not emitted on pressing Enter.
                idx = self.currentIndex()
                if idx.isValid():
                    self.item_chosen(idx)
                self.hide()
                e.accept()
                return True
            if key == Qt.Key.Key_Tab:
                idx = self.currentIndex()
                if idx.isValid():
                    self.item_chosen(idx)
                    self.hide()
                elif self.tab_accepts_uncompleted_text:
                    self.hide()
                    self.apply_current_text.emit()
                elif self.model().rowCount() > 0:
                    self.next_match()
                e.accept()
                return True
            if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                # Let the list view handle these keys
                return False
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self.next_match(previous=key == Qt.Key.Key_Up)
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
        elif ismacos and etype == QEvent.Type.InputMethodQuery and e.queries() == (
            Qt.InputMethodQuery.ImHints | Qt.InputMethodQuery.ImEnabled) and self.isVisible():
            # In Qt 5 the Esc key causes this event and the line edit does not
            # handle it, which causes the parent dialog to be closed
            # See https://bugreports.qt-project.org/browse/QTBUG-41806
            e.accept()
            return True
        elif etype == QEvent.Type.MouseButtonPress and hasattr(e, 'globalPos') and not self.rect().contains(self.mapFromGlobal(e.globalPos())):
            # A click outside the popup, close it
            if isinstance(widget, QComboBox):
                # This workaround is needed to ensure clicking on the drop down
                # arrow of the combobox closes the popup
                opt = QStyleOptionComboBox()
                widget.initStyleOption(opt)
                sc = widget.style().hitTestComplexControl(QStyle.ComplexControl.CC_ComboBox, opt, widget.mapFromGlobal(e.globalPos()), widget)
                if sc == QStyle.SubControl.SC_ComboBoxArrow:
                    QTimer.singleShot(0, self.hide)
                    e.accept()
                    return True
            self.hide()
            e.accept()
            return True
        elif etype in (QEvent.Type.InputMethod, QEvent.Type.ShortcutOverride):
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

    def __init__(self, parent=None, completer_widget=None, sort_func=sort_key, strip_completion_entries=True):
        QLineEdit.__init__(self, parent)
        self.setClearButtonEnabled(True)

        self.sep = ','
        self.space_before_sep = False
        self.add_separator = True
        self.original_cursor_pos = None
        completer_widget = (self if completer_widget is None else
                completer_widget)

        self.mcompleter = Completer(completer_widget, sort_func=sort_func, strip_completion_entries=strip_completion_entries)
        self.mcompleter.item_selected.connect(self.completion_selected,
                type=Qt.ConnectionType.QueuedConnection)
        self.mcompleter.apply_current_text.connect(self.apply_current_text,
                type=Qt.ConnectionType.QueuedConnection)
        self.mcompleter.relayout_needed.connect(self.relayout)
        self.mcompleter.setFocusProxy(completer_widget)
        self.textEdited.connect(self.text_edited)
        self.no_popup = False

    # Interface {{{
    def set_sort_func(self, sort_func):
        self.mcompleter.model().sort_func = sort_func

    def update_items_cache(self, complete_items):
        self.all_items = complete_items

    def set_separator(self, sep):
        self.sep = sep

    def set_space_before_sep(self, space_before):
        self.space_before_sep = space_before

    def set_add_separator(self, what):
        self.add_separator = bool(what)

    @property
    def all_items(self):
        return self.mcompleter.model().all_items

    @all_items.setter
    def all_items(self, items):
        self.mcompleter.model().set_items(items)

    @property
    def disable_popup(self):
        return self.mcompleter.disable_popup

    @disable_popup.setter
    def disable_popup(self, val):
        self.mcompleter.disable_popup = bool(val)

    def set_elide_mode(self, val):
        self.mcompleter.setTextElideMode(val)
    # }}}

    def event(self, ev):
        # See https://bugreports.qt.io/browse/QTBUG-46911
        try:
            if ev.type() == QEvent.Type.ShortcutOverride and (
                    ev.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and (
                        ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier) == Qt.KeyboardModifier.ControlModifier):
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
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.mcompleter.scroll_to(orig)

    def relayout(self):
        self.mcompleter.popup()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

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
        text = str(self.text())
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
            curtext = str(self.text())
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
        before_text, after_text = self.get_completed_text(str(text))
        self.setText(before_text + after_text)
        self.setCursorPosition(len(before_text))
        self.item_selected.emit(text)

    def apply_current_text(self):
        if self.sep is not None:
            txt = str(self.text())
            sep_pos = txt.rfind(self.sep)
            if sep_pos:
                ntxt = txt[sep_pos+1:].strip()
                self.completion_selected(ntxt)


class EditWithComplete(EnComboBox):

    item_selected = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        EnComboBox.__init__(self, *args)
        self.setLineEdit(LineEdit(
            self, completer_widget=self, sort_func=kwargs.get('sort_func', sort_key),
            strip_completion_entries=kwargs.get('strip_completion_entries', False)))
        self.lineEdit().item_selected.connect(self.item_selected)
        self.setCompleter(None)
        self.eat_focus_out = True
        self.installEventFilter(self)

    # Interface {{{

    def set_sort_func(self, sort_func):
        self.lineEdit().set_sort_func(sort_func)

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
        what = str(what) if what else ''
        self.setText(what)
        self.lineEdit().selectAll()

    @property
    def all_items(self):
        return self.lineEdit().all_items

    @all_items.setter
    def all_items(self, val):
        self.lineEdit().all_items = val

    @property
    def disable_popup(self):
        return self.lineEdit().disable_popup

    @disable_popup.setter
    def disable_popup(self, val):
        self.lineEdit().disable_popup = bool(val)

    def set_elide_mode(self, val):
        self.lineEdit().set_elide_mode(val)

    def set_clear_button_enabled(self, val=True):
        self.lineEdit().setClearButtonEnabled(bool(val))
    # }}}

    def text(self):
        return self.lineEdit().text()

    def selectAll(self):
        self.lineEdit().selectAll()

    def setText(self, val):
        le = self.lineEdit()
        le.no_popup = True
        le.setText(val)
        le.no_popup = False

    def home(self, mark=False):
        self.lineEdit().home(mark)

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
        if self.eat_focus_out and self is obj and etype == QEvent.Type.FocusOut:
            if c.isVisible():
                return True
        return EnComboBox.eventFilter(self, obj, e)


if __name__ == '__main__':
    from qt.core import QDialog, QVBoxLayout
    from calibre.gui2 import Application
    app = Application([])
    d = QDialog()
    d.setLayout(QVBoxLayout())
    le = EditWithComplete(d)
    d.layout().addWidget(le)
    items = ['oane\n line2\n line3', 'otwo', 'othree', 'ooone', 'ootwo', 'other', 'odd', 'over', 'orc', 'oven', 'owe',
        'oothree', 'a1', 'a2','Edgas', 'Èdgar', 'Édgaq', 'Edgar', 'Édgar']
    le.update_items_cache(items)
    le.show_initial_value('')
    d.exec()
