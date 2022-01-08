#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QPoint, QRect, QSize, QSizePolicy, QStyle, QStyleOption, QStylePainter, Qt,
    QToolBar, QToolButton, QWidget, pyqtSignal
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
        p = QStylePainter(self)
        p.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorToolBarSeparator, self.style_option())


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

    def __repr__(self):
        return f'Button({self.toolTip()})'


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


class LayoutItem:

    def __init__(self, w):
        self.widget = w
        self.sz = sz = w.sizeHint()
        self.width = sz.width()
        self.height = sz.height()


class Group:

    def __init__(self, parent=None, leading_separator=None):
        self.items = []
        self.width = self.height = 0
        self.parent = parent
        self.leading_separator = leading_separator

    def __bool__(self):
        return bool(self.items)

    def smart_spacing(self, horizontal=True):
        p = self.parent
        if p is None:
            return -1
        if p.isWidgetType():
            which = QStyle.PixelMetric.PM_LayoutHorizontalSpacing if horizontal else QStyle.PixelMetric.PM_LayoutVerticalSpacing
            return p.style().pixelMetric(which, None, p)
        return p.spacing()

    def layout_spacing(self, wid, horizontal=True):
        ans = self.smart_spacing(horizontal)
        if ans != -1:
            return ans
        return wid.style().layoutSpacing(
            QSizePolicy.ControlType.ToolButton,
            QSizePolicy.ControlType.ToolButton,
            Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)

    def add_widget(self, w):
        item = LayoutItem(w)
        self.items.append(item)
        hs, vs = self.layout_spacing(w), self.layout_spacing(w, False)
        if self.items:
            self.width += hs
        self.width += item.width
        self.height = max(vs + item.height, self.height)


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
        if apply_geometry:
            for item in self.items:
                if isinstance(item, Separator):
                    item.setGeometry(0, 0, 0, 0)

        def commit_line():
            while current_line and isinstance(current_line[-1], Separator):
                current_line.pop()
            if current_line:
                lines.append((line_height, current_line))

        groups = []
        current_group = Group(self.parent())
        for wid in self.items:
            if not wid.isVisible() or (not current_group and isinstance(wid, Separator)):
                continue
            if isinstance(wid, Separator):
                groups.append(current_group)
                current_group = Group(self.parent(), wid)
            else:
                current_group.add_widget(wid)
        if current_group:
            groups.append(current_group)
        x = rect.x()
        y = 0
        line_height = 0
        vs = 0
        for group in groups:
            if current_line and x + group.width >= rect.right():
                commit_line()
                current_line = []
                x = rect.x()
                y += group.height
                group.leading_separator = None
                line_height = 0
            if group.leading_separator:
                current_line.append(group.leading_separator)
                sz = group.leading_separator.sizeHint()
                gmap[group.leading_separator] = x, y, sz
                x += sz.width() + group.layout_spacing(group.leading_separator)
            for item in group.items:
                wid = item.widget
                if not vs:
                    vs = group.layout_spacing(wid, False)
                if apply_geometry:
                    gmap[wid] = x, y, item.sz
                x += item.width + group.layout_spacing(wid)
                current_line.append(wid)
            line_height = group.height

        commit_line()

        if apply_geometry:
            self.applied_geometry = rect
            for line_height, items in lines:
                for wid in items:
                    x, wy, isz = gmap[wid]
                    if isz.height() < line_height:
                        wy += (line_height - isz.height()) // 2
                    if wid.isVisible():
                        wid.setGeometry(QRect(QPoint(x, wy), isz))

        return y + line_height - rect.y()


def create_flow_toolbar(parent=None, icon_size=18, restrict_to_single_line=False):
    if restrict_to_single_line:
        return SingleLineToolBar(parent, icon_size)
    return FlowToolBar(parent, icon_size)
