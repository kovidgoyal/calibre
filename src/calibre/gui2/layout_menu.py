#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import (
    QFontMetrics, QHBoxLayout, QIcon, QMenu, QPainter, QPushButton, QSize,
    QSizePolicy, Qt, QWidget, QStyleOption, QStyle)


ICON_SZ = 64


class LayoutItem(QWidget):

    def __init__(self, button, parent=None):
        QWidget.__init__(self, parent)
        self.mouse_over = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.button = button
        self.text = button.label
        self.setCursor(Qt.PointingHandCursor)
        self.fm = QFontMetrics(self.font())
        self._bi = self._di = None

    @property
    def bright_icon(self):
        if self._bi is None:
            self._bi = self.button.icon().pixmap(ICON_SZ, ICON_SZ)
        return self._bi

    @property
    def dull_icon(self):
        if self._di is None:
            self._di = self.button.icon().pixmap(ICON_SZ, ICON_SZ, mode=QIcon.Disabled)
        return self._di

    def event(self, ev):
        m = None
        et = ev.type()
        if et == ev.Enter:
            m = True
        elif et == ev.Leave:
            m = False
        if m is not None and m != self.mouse_over:
            self.mouse_over = m
            self.update()
        return QWidget.event(self, ev)

    def sizeHint(self):
        br = self.fm.boundingRect(self.text)
        w = max(br.width(), ICON_SZ) + 10
        h = 2 * self.fm.lineSpacing() + ICON_SZ + 8
        return QSize(w, h)

    def paintEvent(self, ev):
        shown = self.button.isChecked()
        ls = self.fm.lineSpacing()
        painter = QPainter(self)
        if self.mouse_over:
            tool = QStyleOption()
            tool.rect = self.rect()
            tool.state = QStyle.State_Raised | QStyle.State_Active | QStyle.State_MouseOver
            s = self.style()
            s.drawPrimitive(QStyle.PE_PanelButtonTool, tool, painter, self)
        painter.drawText(
            0, 0,
            self.width(),
            ls, Qt.AlignCenter | Qt.TextSingleLine, self.text)
        text = _('Hide') if shown else _('Show')
        f = self.font()
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            0, self.height() - ls,
            self.width(),
            ls, Qt.AlignCenter | Qt.TextSingleLine, text)
        x = (self.width() - ICON_SZ) // 2
        y = ls + (self.height() - ICON_SZ - 2 * ls) // 2
        pmap = self.bright_icon if shown else self.dull_icon
        painter.drawPixmap(x, y, pmap)
        painter.end()


class LayoutMenu(QMenu):

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.l = l = QHBoxLayout(self)
        l.setSpacing(20)
        self.items = []
        if parent is None:
            buttons = [
                QPushButton(QIcon(I(i + '.png')), i, self)
                for i in 'search tags cover_flow grid book'.split()]
            for b in buttons:
                b.setVisible(False), b.setCheckable(True), b.setChecked(b.text() in 'tags grid')
                b.label = b.text().capitalize()
        else:
            buttons = parent.layout_buttons
        for b in buttons:
            self.items.append(LayoutItem(b, self))
            l.addWidget(self.items[-1])
        self.current_item = None

    def sizeHint(self):
        return QWidget.sizeHint(self)

    def paintEvent(self, ev):
        return QWidget.paintEvent(self, ev)

    def item_for_ev(self, ev):
        for item in self.items:
            if item.geometry().contains(ev.pos()):
                return item

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
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
        if ev.button() != Qt.LeftButton:
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
    w.exec_()
