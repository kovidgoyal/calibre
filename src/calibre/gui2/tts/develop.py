#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from typing import Literal

from qt.core import QAction, QKeySequence, QPlainTextEdit, QSize, Qt, QTextCursor, QToolBar

from calibre.gui2 import Application
from calibre.gui2.main_window import MainWindow
from calibre.gui2.tts.manager import TTSManager

TEXT = '''\
Demonstration 🐈 of DOCX <3 support in calibre

This document demonstrates the ability of the calibre DOCX Input plugin to convert the various typographic features in a Microsoft Word
(2007 and newer) document. Convert this document to a modern ebook format, such as AZW3 for Kindles or EPUB for other ebook readers,
to see it in action.
'''


class MainWindow(MainWindow):

    def __init__(self, text):
        super().__init__()
        self.display = d = QPlainTextEdit(self)
        self.page_count = 1
        self.toolbar = tb = QToolBar(self)
        self.tts = TTSManager(self)
        self.tts.state_event.connect(self.state_event, type=Qt.ConnectionType.QueuedConnection)
        self.tts.saying.connect(self.saying)
        self.addToolBar(tb)
        self.setCentralWidget(d)
        d.setPlainText(text)
        d.setReadOnly(True)
        self.create_marked_text()
        self.play_action = pa = QAction('Play')
        pa.setShortcut(QKeySequence(Qt.Key.Key_Space))
        pa.triggered.connect(self.play_triggerred)
        self.toolbar.addAction(pa)
        self.stop_action = sa = QAction('Stop')
        sa.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        sa.triggered.connect(self.stop)
        self.toolbar.addAction(sa)
        self.faster_action = fa = QAction('Faster')
        fa.triggered.connect(self.tts.faster)
        self.toolbar.addAction(fa)
        self.slower_action = sa = QAction('Slower')
        self.toolbar.addAction(sa)
        sa.triggered.connect(self.tts.slower)
        self.configure_action = ca = QAction('Configure')
        self.toolbar.addAction(ca)
        ca.triggered.connect(self.tts.configure)
        self.reload_action = ra = QAction('Reload')
        self.toolbar.addAction(ra)
        ra.triggered.connect(self.tts.test_resume_after_reload)

        self.resize(self.sizeHint())

    def stop(self):
        self.update_play_action('Play')
        self.stop_action.setEnabled(False)
        self.tts.stop()
        c = self.display.textCursor()
        c.setPosition(0)
        self.display.setTextCursor(c)

    def create_marked_text(self):
        c = self.display.textCursor()
        c.setPosition(0)
        marked_text = []
        while True:
            marked_text.append(c.position())
            if not c.movePosition(QTextCursor.MoveOperation.NextWord, QTextCursor.MoveMode.KeepAnchor):
                break
            marked_text.append(c.selectedText().replace('\u2029', '\n'))
            c.setPosition(c.position())
        c.setPosition(0)
        self.marked_text = marked_text
        self.display.setTextCursor(c)

    def next_page(self):
        self.page_count += 1
        self.display.setPlainText(f'This is page number {self.page_count}. Pages are turned automatically when the end of a page is reached.')
        self.create_marked_text()

    def update_play_action(self, text):
        self.play_action.setText(text)

    def state_event(self, ev: Literal['begin', 'end', 'cancel', 'pause', 'resume']):
        sb = self.statusBar()
        events = sb.currentMessage().split()
        events.append(ev)
        if len(events) > 16:
            del events[0]
        self.statusBar().showMessage(' '.join(events))
        self.stop_action.setEnabled(ev in ('pause', 'resume', 'begin'))
        if ev == 'cancel':
            self.update_play_action('Play')
        elif ev == 'pause':
            self.update_play_action('Resume')
        elif ev in ('resume', 'begin'):
            self.update_play_action('Pause')
        elif ev == 'end':
            if self.play_action.text() == 'Pause':
                self.next_page()
                self.update_play_action('Play')
                self.play_triggerred()

    def play_triggerred(self):
        if self.play_action.text() == 'Resume':
            self.tts.resume()
        elif self.play_action.text() == 'Pause':
            self.tts.pause()
        else:
            self.tts.speak_marked_text(self.marked_text)

    def saying(self, first, last):
        c = self.display.textCursor()
        c.setPosition(first)
        if last != first:
            c.setPosition(last, QTextCursor.MoveMode.KeepAnchor)
        c.movePosition(QTextCursor.MoveOperation.WordRight, QTextCursor.MoveMode.KeepAnchor)
        self.display.setTextCursor(c)

    def sizeHint(self):
        return QSize(500, 400)


def main():
    app = Application([])
    mw = MainWindow(TEXT)
    mw.set_exception_handler()
    mw.show()
    app.exec()


if __name__ == '__main__':
    main()
