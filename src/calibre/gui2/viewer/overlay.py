#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from PyQt5.Qt import QWidget, Qt, QFontInfo, QLabel, QVBoxLayout

from calibre.gui2.progress_indicator import ProgressIndicator


class LoadingOverlay(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.pi = ProgressIndicator(self, 96, 80)
        self.setVisible(False)
        self.label = QLabel(self)
        self.label.setText('<i>testing with some long and wrap worthy message that should hopefully still render well')
        self.label.setTextFormat(Qt.RichText)
        self.label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.label.setWordWrap(True)
        if parent is None:
            self.resize(300, 300)
        else:
            self.resize(parent.size())
        self.setAutoFillBackground(True)
        pal = self.palette()
        col = pal.color(pal.Window)
        col.setAlphaF(0.8)
        pal.setColor(pal.Window, col)
        self.setPalette(pal)
        self.move(0, 0)
        f = self.font()
        f.setBold(True)
        fm = QFontInfo(f)
        f.setPixelSize(int(fm.pixelSize() * 1.5))
        self.label.setFont(f)
        l.addStretch(10)
        l.addWidget(self.pi)
        l.addWidget(self.label)
        l.addStretch(10)

    def __call__(self, msg=''):
        self.label.setText(msg)
        self.resize(self.parent().size())
        self.move(0, 0)
        self.setVisible(True)
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        self.update()

    def hide(self):
        self.parent().web_view.setFocus(Qt.OtherFocusReason)
        self.pi.stop()
        return QWidget.hide(self)

    def showEvent(self, ev):
        # import time
        # self.st = time.monotonic()
        self.pi.start()

    def hideEvent(self, ev):
        # import time
        # print(1111111, time.monotonic() - self.st)
        self.pi.stop()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    w = LoadingOverlay()
    w.show()
    app.exec_()
