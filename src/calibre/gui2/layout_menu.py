#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QFontMetrics, QHBoxLayout, QIcon, QMenu, QPushButton, QSize, QSizePolicy, QStyle, QStyleOption, QStylePainter, Qt, QWidget


class LayoutItem(QWidget):

    mouse_over = False
    VMARGIN = 4

    def __init__(self, button, parent=None):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.button = button
        self.text = button.label
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fm = QFontMetrics(self.font())

    def update_tips(self):
        self.setToolTip(self.button.toolTip())
        self.setStatusTip(self.button.statusTip())

    def bright_icon(self, height):
        return self.button.icon().pixmap(height, height)

    def dull_icon(self, height):
        return self.button.icon().pixmap(height, height, mode=QIcon.Mode.Disabled)

    def enterEvent(self, ev):
        super().enterEvent(ev)
        if not self.mouse_over:
            self.mouse_over = True
            self.update()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        if self.mouse_over:
            self.mouse_over = False
            self.update()

    def sizeHint(self):
        ICON_SZ = 64
        br = self.fm.boundingRect(self.text)
        w = max(br.width(), ICON_SZ) + 10
        h = 2 * self.fm.lineSpacing() + ICON_SZ + 2 * self.VMARGIN
        return QSize(w, h)

    def paintEvent(self, ev):
        shown = self.button.isChecked()
        ls = self.fm.lineSpacing()
        painter = QStylePainter(self)
        if self.mouse_over:
            tool = QStyleOption()
            tool.initFrom(self)
            tool.rect = self.rect()
            tool.state = QStyle.StateFlag.State_Raised | QStyle.StateFlag.State_Active | QStyle.StateFlag.State_MouseOver
            painter.drawPrimitive(QStyle.PrimitiveElement.PE_PanelButtonTool, tool)
        br = painter.drawText(0, 0, self.width(), ls, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, self.text)
        top = br.bottom()
        bottom = self.height() - ls
        text = _('Hide') if shown else _('Show')
        f = self.font()
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(0, bottom, self.width(), ls, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, text)
        height = bottom - top - 2 * self.VMARGIN
        x = (self.width() - height) // 2
        pmap = self.bright_icon(height) if shown else self.dull_icon(height)
        painter.drawPixmap(x, top + self.VMARGIN, pmap)
        painter.end()


class LayoutMenu(QMenu):

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        l.setSpacing(20)
        self.items = []
        if parent is None:
            buttons = [
                QPushButton(QIcon.ic(i + '.png'), i, self)
                for i in 'search tags cover_flow grid book'.split()]
            for b in buttons:
                b.setVisible(False), b.setCheckable(True), b.setChecked(b.text() in 'tags grid')
                b.label = b.text().capitalize()
        else:
            buttons = parent.layout_buttons
        for b in buttons:
            self.items.append(LayoutItem(b, self))
            l.addWidget(self.items[-1])
            self.aboutToShow.connect(self.about_to_show)
        self.current_item = None

    def about_to_show(self):
        for x in self.items:
            x.update_tips()

    def sizeHint(self):
        return QWidget.sizeHint(self)

    def paintEvent(self, ev):
        return QWidget.paintEvent(self, ev)

    def item_for_ev(self, ev):
        for item in self.items:
            if item.geometry().contains(ev.pos()):
                return item

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            ev.ignore()
            return
        if (ev.pos().isNull() and not ev.screenPos().isNull()) or not self.rect().contains(ev.pos()):
            self.hide()
        self.current_item = self.item_for_ev(ev)
        if self.current_item is not None:
            ev.accept()
        else:
            ev.ignore()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            ev.ignore()
            return
        item = self.item_for_ev(ev)
        if item is not None and item is self.current_item:
            ev.accept()
            self.hide()
            item.button.click()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    w = LayoutMenu()
    w.show()
    w.exec()
