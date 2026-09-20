#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid@kovidgoyal.net>

"""
Support for removing individual entries from the drop down lists of widgets
that remember what was previously typed into them. Matches the behavior of
web browsers: hovering over an entry shows a small remove button at the right
edge of the entry and Shift+Delete removes the entry under the mouse cursor.
"""

from collections.abc import Callable

from qt.core import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QEvent,
    QIcon,
    QObject,
    QPoint,
    QRect,
    QSize,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QToolTip,
    QWidget,
    sip,
)

from calibre.utils.localization import _

MARGIN = 2

# PyQt destroys the Python part of an object as soon as the last reference to
# it from Python goes away, even when the C++ object lives on, for instance
# because it is a child of some other C++ object. The C++ object is then left
# without the Python re-implementations of paint() and eventFilter(), silently
# disabling removal of entries. This happens in practice because the popup
# used by QCompleter has no parent widget, so nothing keeps its children alive
# from Python. Therefore keep the removers alive ourselves.
removers: set[HistoryItemRemover] = set()


class RemovableItemDelegate(QStyledItemDelegate):  # {{{
    "Draws a remove button at the right edge of the item the mouse is over"

    def __init__(self, remover: HistoryItemRemover):
        super().__init__(remover.view)
        self.remover = remover

    def sizeHint(self, option, index):
        ans = super().sizeHint(option, index)
        if isinstance(ans, QSize):
            ans.setWidth(ans.width() + ans.height() + 2 * MARGIN)
        return ans

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Match the behavior of the delegate QCompleter uses for its popup,
        # otherwise the current item is not highlighted in completer popups
        opt.showDecorationSelected = True
        view = self.remover.view
        if view.currentIndex() == index:
            opt.state |= QStyle.StateFlag.State_HasFocus
        hovered = index.row() == self.remover.hovered_row
        if hovered:
            opt.state |= QStyle.StateFlag.State_MouseOver
        widget = opt.widget or view
        style = widget.style() or QApplication.style()
        assert style is not None
        button_rect = self.remover.button_rect(opt.rect)
        if opt.text:
            # Elide the text ourselves so that it never runs underneath the
            # remove button. Space for the button is always reserved so that
            # the text does not move around as the mouse moves.
            text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
            available = max(0, button_rect.left() - MARGIN - text_rect.left())
            opt.text = opt.fontMetrics.elidedText(opt.text, opt.textElideMode, available)
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        if hovered:
            mode = QIcon.Mode.Selected if self.remover.pressed_row == index.row() else QIcon.Mode.Normal
            self.remover.icon.paint(painter, button_rect, Qt.AlignmentFlag.AlignCenter, mode)


# }}}


class HistoryItemRemover(QObject):
    """
    Allow removing individual entries from the drop down list shown by view.
    remove_item() is called with the text of the entry that is to be removed,
    it is responsible for actually removing the entry from both the model used
    by the view and from wherever the history is persisted.
    """

    def __init__(
        self,
        view: QAbstractItemView,
        remove_item: Callable[[str], None],
        hide_popup: Callable[[], None] | None = None,
        restore_current_row: bool = True,
        text_role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole,
    ):
        super().__init__(view)
        self.view = view
        self.remove_item = remove_item
        self.hide_popup = view.hide if hide_popup is None else hide_popup
        # the role under which the model stores the un-mangled text of an entry
        self.text_role = text_role
        # Highlighting an entry in a QCompleter popup replaces the text in the
        # widget being completed, so it must not be done behind the user's back
        self.restore_current_row = restore_current_row
        self.hovered_row = -1
        self.pressed_row = -1
        self.last_mouse_pos: QPoint | None = None
        self.icon = QIcon.ic('close.png')
        self.tooltip_text = _('Remove this entry from the history (Shift+Delete)')
        view.setMouseTracking(True)
        viewport = view.viewport()
        assert viewport is not None
        viewport.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.delegate = RemovableItemDelegate(self)
        view.setItemDelegate(self.delegate)
        view.installEventFilter(self)
        viewport.installEventFilter(self)
        # QComboBox shows its view inside a popup container widget and key
        # presses are delivered to the container rather than to the view
        window = view.window()
        self.popup_container = None
        if window is not None and window is not view and window.windowType() == Qt.WindowType.Popup:
            self.popup_container = window
            window.installEventFilter(self)
        removers.add(self)
        view.destroyed.connect(self.view_destroyed)

    def view_destroyed(self) -> None:
        removers.discard(self)

    # Item lookup {{{
    def button_rect(self, item_rect: QRect) -> QRect:
        """
        The rectangle occupied by the remove button for an entry occupying
        item_rect, in viewport co-ordinates. item_rect can extend past the
        right edge of the viewport, when an entry is wider than the viewport
        or when there is a vertical scrollbar, so the button is clamped to the
        visible area, otherwise it is drawn where it cannot be seen or clicked.
        """
        right = item_rect.right()
        viewport = self.view.viewport()
        if viewport is not None:
            right = min(right, viewport.width() - 1)
        sz = max(8, item_rect.height() - 2 * MARGIN)
        return QRect(right - sz - MARGIN, item_rect.top() + MARGIN, sz, sz)

    def set_hovered_row(self, row: int) -> None:
        if row != self.hovered_row:
            self.hovered_row = row
            self.update_view()

    def update_view(self) -> None:
        viewport = self.view.viewport()
        if viewport is not None:
            viewport.update()

    def row_at(self, pos: QPoint) -> int:
        idx = self.view.indexAt(pos)
        return idx.row() if idx.isValid() else -1

    def row_for_button_at(self, pos: QPoint) -> int:
        idx = self.view.indexAt(pos)
        if idx.isValid() and self.button_rect(self.view.visualRect(idx)).contains(pos):
            return idx.row()
        return -1

    def remember_mouse_pos(self, viewport: QWidget, pos: QPoint) -> None:
        "Remember where the mouse is, in global co-ordinates, so that it survives the popup being moved"
        self.last_mouse_pos = viewport.mapToGlobal(pos)

    def refresh_hovered_row(self) -> None:
        """
        Re-calculate which entry is under the mouse, using the position from
        the last mouse event. Needed because entries move under a stationary
        mouse when the popup is re-shown, re-populated or scrolled. Note that
        QCursor.pos() is deliberately not used, as it is unreliable on some
        platforms, in particular while a popup grab is active on Wayland. This
        never hides the button, clearing is done in response to the mouse
        actually leaving the popup.
        """
        viewport = self.view.viewport()
        if viewport is None or self.last_mouse_pos is None or not viewport.isVisible() or not viewport.underMouse():
            return
        pos = viewport.mapFromGlobal(self.last_mouse_pos)
        if viewport.rect().contains(pos):
            self.set_hovered_row(self.row_at(pos))

    def text_for_row(self, row: int) -> str:
        model = self.view.model()
        if model is None or row < 0 or row >= model.rowCount():
            return ''
        index = model.index(row, 0)
        ans = index.data(self.text_role)
        if not isinstance(ans, str):
            ans = index.data(Qt.ItemDataRole.DisplayRole)
        return ans if isinstance(ans, str) else ''

    def row_to_remove(self) -> int:
        "The entry the mouse is over, falling back to the highlighted entry"
        if self.hovered_row > -1:
            return self.hovered_row
        idx = self.view.currentIndex()
        return idx.row() if idx.isValid() else -1

    # }}}

    def remove_row(self, row: int) -> None:
        text = self.text_for_row(row)
        if not text:
            return
        self.pressed_row = -1
        was_current = self.view.currentIndex().row() == row
        self.remove_item(text)
        model = self.view.model()
        if model is None or model.rowCount() < 1:
            self.hovered_row = -1
            self.hide_popup()
            return
        if was_current and self.restore_current_row and not self.view.currentIndex().isValid():
            # highlight the entry that has taken the place of the removed one,
            # so that repeated presses of Shift+Delete work
            self.view.setCurrentIndex(model.index(min(row, model.rowCount() - 1), 0))
        # The entries have moved up, so recalculate which one is under the
        # mouse, allowing repeated clicks on the remove button to work
        self.refresh_hovered_row()
        self.update_view()

    def is_remove_key(self, event) -> bool:
        try:
            key = event.key()
            mods = event.modifiers()
        except AttributeError:
            return False
        if key != Qt.Key.Key_Delete or not (mods & Qt.KeyboardModifier.ShiftModifier):
            return False
        # ignore modifiers that are present based on keyboard layout/numlock
        # state, such as Keypad and GroupSwitch
        return not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier))

    def eventFilter(self, a0, a1):
        if a0 is None or a1 is None or sip.isdeleted(self.view):
            return False
        etype = a1.type()
        viewport = self.view.viewport()
        if a0 is viewport:
            return self.filter_viewport_event(viewport, etype, a1)
        if a0 is self.view or a0 is self.popup_container:
            if etype in (QEvent.Type.Hide, QEvent.Type.FocusOut):
                self.pressed_row = -1
                self.set_hovered_row(-1)
            elif etype in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride) and self.is_remove_key(a1):
                row = self.row_to_remove()
                if row < 0:  # no entry to remove, let the key be handled normally
                    return False
                if etype == QEvent.Type.KeyPress:
                    self.remove_row(row)
                a1.accept()
                return True
        return False

    def filter_viewport_event(self, viewport: QWidget, etype: QEvent.Type, event) -> bool:
        if etype == QEvent.Type.Paint:
            # Mouse events alone are not enough, as the popup is often shown,
            # re-populated or scrolled under a stationary mouse cursor, which
            # moves a different entry under the mouse without any mouse event
            self.refresh_hovered_row()
        elif etype in (QEvent.Type.MouseMove, QEvent.Type.HoverMove, QEvent.Type.HoverEnter):
            pos = event.position().toPoint()
            self.remember_mouse_pos(viewport, pos)
            self.set_hovered_row(self.row_at(pos))
        elif etype in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self.set_hovered_row(-1)
        elif etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                row = self.row_for_button_at(event.position().toPoint())
                if row > -1:
                    self.pressed_row = row
                    self.update_view()
                    event.accept()
                    return True
        elif etype == QEvent.Type.MouseButtonDblClick:
            if self.row_for_button_at(event.position().toPoint()) > -1:
                event.accept()
                return True
        elif etype == QEvent.Type.MouseButtonRelease:
            row, self.pressed_row = self.pressed_row, -1
            if row > -1:
                self.update_view()
                if event.button() == Qt.MouseButton.LeftButton and self.row_for_button_at(event.position().toPoint()) == row:
                    self.remove_row(row)
                event.accept()
                return True
        elif etype == QEvent.Type.ToolTip:
            if self.row_for_button_at(event.pos()) > -1:
                QToolTip.showText(event.globalPos(), self.tooltip_text, viewport)
                event.accept()
                return True
        return False


def enable_item_removal_for_combobox(combo: QComboBox, remove_item: Callable[[str], None]) -> HistoryItemRemover | None:
    "Allow removing individual entries from the drop down list of an editable combobox"
    view = combo.view()
    if view is None:
        return None
    return HistoryItemRemover(view, remove_item, hide_popup=combo.hidePopup)


def remove_item_from_combobox(combo: QComboBox, item: str) -> bool:
    """
    Remove item from the list of entries in combo without disturbing the text
    the user has typed into it. Returns True iff the item was found.
    """
    idx = combo.findText(item, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive)
    if idx < 0:
        return False
    le = combo.lineEdit()
    text = combo.currentText()
    cursor_pos = le.cursorPosition() if le is not None else 0
    blocked = combo.blockSignals(True)
    le_blocked = le.blockSignals(True) if le is not None else False
    try:
        combo.removeItem(idx)
        if le is not None:
            combo.setEditText(text)
            le.setCursorPosition(cursor_pos)
    finally:
        combo.blockSignals(blocked)
        if le is not None:
            le.blockSignals(le_blocked)
    return True
