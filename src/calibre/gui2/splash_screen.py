#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import (
    QApplication, QBrush, QColor, QFont, QFontMetrics, QPen, QPixmap, QSplashScreen,
    Qt
)

from calibre.constants import __appname__, numeric_version
from calibre.utils.monotonic import monotonic
from polyglot.builtins import unicode_type


class SplashScreen(QSplashScreen):

    TITLE_SIZE = 20  # pt
    BODY_SIZE = 12  # pt
    FOOTER_SIZE = 9  # pt
    LOGO_SIZE = 96  # px
    WIDTH = 550  # px

    def __init__(self, develop=False):
        self.drawn_once = False
        self.develop = develop
        self.title_font = f = QFont()
        f.setPointSize(self.TITLE_SIZE)
        f.setBold(True)
        self.title_height = QFontMetrics(f).lineSpacing() + 2
        self.body_font = f = QFont()
        f.setPointSize(self.BODY_SIZE)
        self.line_height = QFontMetrics(f).lineSpacing()
        self.total_height = max(self.LOGO_SIZE, self.title_height + 3 * self.line_height)
        self.num_font = f = QFont()
        f.setPixelSize(self.total_height)
        f.setItalic(True), f.setBold(True)
        f = QFontMetrics(f)
        self.num_ch = unicode_type(max(3, numeric_version[0]))
        self.footer_font = f = QFont()
        f.setPointSize(self.FOOTER_SIZE)
        f.setItalic(True)
        self.dpr = QApplication.instance().devicePixelRatio()
        self.pmap = QPixmap(I('library.png', allow_user_override=False))
        self.pmap.setDevicePixelRatio(self.dpr)
        self.pmap = self.pmap.scaled(int(self.dpr * self.LOGO_SIZE), int(self.dpr * self.LOGO_SIZE), transformMode=Qt.SmoothTransformation)
        self.light_brush = QBrush(QColor('#F6F3E9'))
        self.dark_brush = QBrush(QColor('#39322B'))
        pmap = QPixmap(int(self.WIDTH * self.dpr), int(self.total_height * self.dpr))
        pmap.setDevicePixelRatio(self.dpr)
        pmap.fill(Qt.transparent)
        QSplashScreen.__init__(self, pmap)
        self.setWindowTitle(__appname__)

    def drawContents(self, painter):
        self.drawn_once = True
        painter.save()
        painter.setRenderHint(painter.TextAntialiasing, True)
        painter.setRenderHint(painter.Antialiasing, True)
        pw = self.LOGO_SIZE
        height = max(pw, self.total_height)
        width = self.width()

        # Draw frame
        y = (self.height() - height) // 2
        bottom = y + height
        painter.fillRect(0, y, width, height, self.light_brush)
        painter.fillRect(0, y, width, self.title_height, self.dark_brush)
        painter.fillRect(0, y, pw, height, self.dark_brush)
        dy = (height - self.LOGO_SIZE) // 2
        painter.drawPixmap(0, y + dy, self.pmap)

        # Draw number
        painter.setFont(self.num_font)
        num_width = painter.boundingRect(0, 0, 0, 0, Qt.AlignCenter | Qt.TextSingleLine, self.num_ch).width() + 12
        num_x = width - num_width
        painter.setPen(QPen(QColor('#d6b865')))
        painter.drawText(num_x, y, num_width, height, Qt.AlignCenter | Qt.TextSingleLine, self.num_ch)

        # Draw title
        x = pw + 10
        width -= num_width + 5 + x
        painter.setFont(self.title_font)
        painter.drawText(x, y, width, self.title_height, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, "CALIBRE")

        # Draw starting up message
        y += self.title_height + 5
        painter.setPen(QPen(self.dark_brush.color()))
        painter.setFont(self.body_font)
        br = painter.drawText(x, y, width, self.line_height, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine, _(
            'Starting up, please wait...'))
        starting_up_bottom = br.bottom()

        # Draw footer
        m = self.message()
        if m and m.strip():
            painter.setFont(self.footer_font)
            b = max(starting_up_bottom + 5, bottom - self.line_height)
            painter.drawText(x, b, width, self.line_height, Qt.AlignLeft | Qt.AlignTop | Qt.TextSingleLine, m)

        painter.restore()

    def show_message(self, msg):
        self.showMessage(msg)
        self.wait_for_draw()

    def wait_for_draw(self):
        # Without this the splash screen is not painted on linux and windows
        self.drawn_once = False
        st = monotonic()
        while not self.drawn_once and (monotonic() - st < 0.1):
            QApplication.instance().processEvents()

    def keyPressEvent(self, ev):
        if not self.develop:
            return QSplashScreen.keyPressEvent(self, ev)
        ev.accept()
        QApplication.instance().quit()


def main():
    from calibre.gui2 import Application
    app = Application([])
    spl = SplashScreen(develop=True)
    spl.show()
    spl.show_message('Testing the splash screen message...')
    app.exec_()


if __name__ == '__main__':
    main()
