#!/usr/bin/env python
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>


from typing import cast

from qt.core import (
    QBoxLayout,
    QEvent,
    QFontMetrics,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QPainter,
    QPushButton,
    QSize,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QStylePainter,
    Qt,
    QWidget,
)

from calibre.utils.localization import _


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

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self.mouse_over:
            self.mouse_over = True
            self.update()

    def leaveEvent(self, a0):
        super().leaveEvent(a0)
        if self.mouse_over:
            self.mouse_over = False
            self.update()

    def sizeHint(self):
        ICON_SZ = 64
        br = self.fm.boundingRect(self.text)
        w = max(br.width(), ICON_SZ) + 10
        h = 2 * self.fm.lineSpacing() + ICON_SZ + 2 * self.VMARGIN
        return QSize(w, h)

    def paintEvent(self, a0):
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
        assert br is not None
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


class LayoutMenuInner(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.l = l = QHBoxLayout(self)
        l.setSpacing(20)
        self.items = []
        self.initialized = False

    @property
    def gui(self):
        _parent = self.parent()
        assert _parent is not None
        return _parent.parent()

    def delayed_init(self):
        if not self.initialized:
            self.initialized = True
            gui = self.gui
            if not hasattr(gui, 'layout_buttons'):
                buttons = [
                    QPushButton(QIcon.ic(i + '.png'), i, self)
                    for i in 'search tags cover_flow grid book'.split()]
                for b in buttons:
                    b.setVisible(False), b.setCheckable(True), b.setChecked(b.text() in 'tags grid')
                    setattr(b, 'label', b.text().capitalize())
            else:
                buttons = gui.layout_buttons
            l = self.layout()
            assert l is not None
            for b in buttons:
                self.items.append(LayoutItem(b, self))
                cast(QBoxLayout, l).addWidget(self.items[-1], alignment=Qt.AlignmentFlag.AlignBottom)
        self.current_item = None
        for x in self.items:
            x.update_tips()
        self.resize(self.sizeHint())

    def paintEvent(self, a0):
        painter = QPainter(self)
        col = self.palette().window().color()
        col.setAlphaF(0.9)
        painter.fillRect(self.rect(), col)
        super().paintEvent(a0)

    def item_for_ev(self, ev):
        for item in self.items:
            if item.geometry().contains(ev.pos()):
                return item

    def mousePressEvent(self, a0):
        if a0.button() != Qt.MouseButton.LeftButton:
            a0.ignore()
            return
        self.current_item = self.item_for_ev(a0)
        if self.current_item is not None:
            a0.accept()
        else:
            a0.ignore()

    def mouseReleaseEvent(self, a0):
        if a0.button() != Qt.MouseButton.LeftButton:
            a0.ignore()
            return
        item = self.item_for_ev(a0)
        if item is not None and item is self.current_item:
            a0.accept()
            menu_parent = self.parent()
            assert menu_parent is not None
            assert isinstance(menu_parent, QWidget)
            menu_parent.hide()
            item.button.click()

    def handle_key_press(self, ev):
        q = QKeySequence(ev.keyCombination())
        for item in self.items:
            sc = item.button.shortcut
            if callable(sc):
                sc = item.button.shortcut()
            else:
                sc = QKeySequence.fromString(sc)
            if sc.matches(q) == QKeySequence.SequenceMatch.ExactMatch:
                menu_parent = self.parent()
                assert menu_parent is not None
                assert isinstance(menu_parent, QWidget)
                menu_parent.hide()
                item.button.click()
                ev.accept()
                break


class LayoutMenu(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.setVisible(False)
        self.inner = LayoutMenuInner(self)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def show(self):
        self.inner.delayed_init()
        parent = self.parent()
        assert parent is not None
        assert isinstance(parent, QWidget)
        self.move(0, 0)
        self.resize(parent.rect().size())
        r = parent.rect()
        y = r.height()
        if hasattr(parent, 'layout_button'):
            lb = cast(QWidget, parent.layout_button)
            y = lb.mapTo(parent, lb.rect().topLeft()).y()
        self.inner.move(r.width() - self.inner.size().width(), y - self.inner.size().height())
        super().show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def event(self, a0):
        if a0.type() == QEvent.Type.ShortcutOverride and self.isVisible():
            a0.accept()
        return super().event(a0)

    def keyPressEvent(self, a0):
        if a0.matches(QKeySequence.StandardKey.Cancel):
            self.hide()
        else:
            self.inner.handle_key_press(a0)

    def mousePressEvent(self, a0):
        if a0.button() != Qt.MouseButton.LeftButton:
            a0.ignore()
            return
        if self.inner.rect().contains(a0.pos()):
            a0.ignore()
        else:
            self.hide()


if __name__ == '__main__':
    from qt.core import QMainWindow

    from calibre.gui2 import Application
    app = Application([])
    w = QMainWindow()
    m = LayoutMenu(w)
    w.show()
    m.show()
    app.exec()
