#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QPainter, QPoint, QRect, QSize, QSizePolicy, QStyle, QStyleOption, Qt, QToolBar,
    QToolButton, QWidget, pyqtSignal
)


class Separator(QWidget):

    def __init__(self, icon_size, parent=None):
        super().__init__(parent)
        self.desired_height = icon_size.height() * 0.85

    def style_option(self):
        opt = QStyleOption()
        opt.initFrom(self)
        opt.state |= QStyle.StateFlag.State_Horizontal
        return opt

    def sizeHint(self):
        width = self.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarSeparatorExtent, self.style_option(), self)
        return QSize(width, int(self.devicePixelRatioF() * self.desired_height))

    def paintEvent(self, ev):
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorToolBarSeparator, self.style_option(), p, self)


class Button(QToolButton):

    layout_needed = pyqtSignal()

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.setAutoRaise(True)
        action.changed.connect(self.update_state)
        self.update_state()
        self.clicked.connect(self.action.trigger)

    def update_state(self):
        ac = self.action
        self.setIcon(ac.icon())
        self.setToolTip(ac.toolTip() or self.action.text())
        self.setEnabled(ac.isEnabled())
        self.setCheckable(ac.isCheckable())
        self.setChecked(ac.isChecked())
        self.setMenu(ac.menu())
        old = self.isVisible()
        self.setVisible(ac.isVisible())
        if self.isVisible() != old:
            self.layout_needed.emit()


class SingleLineToolBar(QToolBar):

    def __init__(self, parent=None, icon_size=18):
        super().__init__(parent)
        self.setIconSize(QSize(icon_size, icon_size))

    def add_action(self, ac, popup_mode=QToolButton.ToolButtonPopupMode.DelayedPopup):
        self.addAction(ac)
        w = self.widgetForAction(ac)
        w.setPopupMode(popup_mode)

    def add_separator(self):
        self.addSeparator()


class FlowToolBar(QWidget):

    def __init__(self, parent=None, icon_size=18):
        super().__init__(parent)
        self.icon_size = QSize(icon_size, icon_size)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.items = []
        self.button_map = {}
        self.applied_geometry = QRect(0, 0, 0, 0)

    def add_action(self, ac, popup_mode=QToolButton.ToolButtonPopupMode.DelayedPopup):
        w = Button(ac, self)
        w.setPopupMode(popup_mode)
        w.setIconSize(self.icon_size)
        self.button_map[ac] = w
        self.items.append(w)
        w.layout_needed.connect(self.updateGeometry)
        self.updateGeometry()

    def add_separator(self):
        self.items.append(Separator(self.icon_size, self))
        self.updateGeometry()

    def smart_spacing(self, horizontal=True):
        p = self.parent()
        if p is None:
            return -1
        if p.isWidgetType():
            which = QStyle.PixelMetric.PM_LayoutHorizontalSpacing if horizontal else QStyle.PixelMetric.PM_LayoutVerticalSpacing
            return p.style().pixelMetric(which, None, p)
        return p.spacing()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        return size
    sizeHint = minimumSize

    def paintEvent(self, ev):
        if self.applied_geometry != self.rect():
            self.do_layout(self.rect(), apply_geometry=True)
        super().paintEvent(ev)

    def do_layout(self, rect, apply_geometry=False):
        x, y = rect.x(), rect.y()

        line_height = 0

        def layout_spacing(wid, horizontal=True):
            ans = self.smart_spacing(horizontal)
            if ans != -1:
                return ans
            return wid.style().layoutSpacing(
                QSizePolicy.ControlType.ToolButton,
                QSizePolicy.ControlType.ToolButton,
                Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)

        lines, current_line = [], []
        gmap = {}
        for i, wid in enumerate(self.items):
            prev_wid = self.items[i - 1] if i else None
            if isinstance(wid, Button) and not wid.isVisible():
                continue
            isz = wid.sizeHint()
            hs, vs = layout_spacing(wid), layout_spacing(wid, False)

            next_x = x + isz.width() + hs
            wid.setVisible(True)
            if isinstance(wid, Separator) and isinstance(prev_wid, Separator):
                wid.setVisible(False)
            if next_x - hs > rect.right() and line_height > 0:
                if isinstance(prev_wid, Separator):
                    prev_wid.setVisible(False)
                if isinstance(wid, Separator):
                    wid.setVisible(False)
                    continue
                x = rect.x()
                y = y + line_height + vs
                next_x = x + isz.width() + hs
                lines.append((line_height, current_line))
                current_line = []
                line_height = 0
            if apply_geometry:
                gmap[wid] = x, y, isz
            x = next_x
            line_height = max(line_height, isz.height())
            current_line.append((wid, isz.height()))

        lines.append((line_height, current_line))

        if apply_geometry:
            self.applied_geometry = rect
            for line_height, items in lines:
                for wid, item_height in items:
                    x, wy, isz = gmap[wid]
                    if item_height < line_height:
                        wy += (line_height - item_height) // 2
                    wid.setGeometry(QRect(QPoint(x, wy), isz))

        return y + line_height - rect.y()


def create_flow_toolbar(parent=None, icon_size=18, restrict_to_single_line=False):
    if restrict_to_single_line:
        return SingleLineToolBar(parent, icon_size)
    return FlowToolBar(parent, icon_size)
