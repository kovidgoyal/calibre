#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

from PyQt5.Qt import Qt, QSplashScreen, QIcon, QApplication, QTransform, QPainterPath, QBrush

from calibre.constants import __appname__, iswindows
from calibre.utils.monotonic import monotonic


class SplashScreen(QSplashScreen):

    def __init__(self, develop=False):
        self.drawn_once = False
        self.develop = develop
        pmap = QIcon(I('library.png', allow_user_override=False)).pixmap(512, 512)
        QSplashScreen.__init__(self, pmap)
        self.setWindowTitle(__appname__)

    def drawContents(self, painter):
        self.drawn_once = True
        painter.save()
        painter.setPen(Qt.black)
        painter.setRenderHint(painter.TextAntialiasing, True)
        painter.setRenderHint(painter.Antialiasing, True)
        f = painter.font()
        f.setPixelSize(18)
        painter.setFont(f)
        t = QTransform()
        t.translate(330, 450)
        painter.setTransform(t)
        painter.rotate(-98)
        left_margin = 25
        if iswindows:
            # On windows Qt cannot anti-alias rotated text
            p = QPainterPath()
            p.addText(left_margin, 0, f, self.message())
            painter.fillPath(p, QBrush(Qt.black))
        else:
            painter.drawText(left_margin, 0, self.message())
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
