#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QAction, QKeySequence, QPlainTextEdit, QSize, Qt, QTextCursor, QTextToSpeech, QToolBar

from calibre.gui2 import Application
from calibre.gui2.main_window import MainWindow
from calibre.gui2.tts2.manager import TTSManager

TEXT = '''\
Demonstration 😹 🐈 of DOCX support in calibre

This document demonstrates the ability of the calibre DOCX Input plugin to convert the various typographic features in a Microsoft Word
(2007 and newer) document. Convert this document to a modern ebook format, such as AZW3 for Kindles or EPUB for other ebook readers,
to see it in action.

There is support for images, tables, lists, footnotes, endnotes, links, dropcaps and various types of text and paragraph level formatting.

To see the DOCX conversion in action, simply add this file to calibre using the “Add Books” button and then click “Convert”.
Set the output format in the top right corner of the conversion dialog to EPUB or AZW3 and click “OK”.
'''


class MainWindow(MainWindow):

    def __init__(self, text):
        super().__init__()
        self.display = d = QPlainTextEdit(self)
        self.toolbar = tb = QToolBar(self)
        self.tts = TTSManager(self)
        self.tts.state_changed.connect(self.state_changed, type=Qt.ConnectionType.QueuedConnection)
        self.tts.saying.connect(self.saying)
        self.addToolBar(tb)
        self.setCentralWidget(d)
        d.setPlainText(text)
        d.setReadOnly(True)
        c = d.textCursor()
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
        self.play_action = pa = QAction('Play')
        pa.setShortcut(QKeySequence(Qt.Key.Key_Space))
        pa.triggered.connect(self.toggled)
        self.toolbar.addAction(pa)
        self.stop_action = sa = QAction('Stop')
        sa.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        sa.triggered.connect(self.tts.stop)
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

        self.state_changed(self.tts.state)
        self.resize(self.sizeHint())

    def state_changed(self, state):
        self.statusBar().showMessage(str(state))
        if state in (QTextToSpeech.State.Ready, QTextToSpeech.State.Paused, QTextToSpeech.State.Error):
            self.play_action.setChecked(False)
            if state is QTextToSpeech.State.Ready:
                c = self.display.textCursor()
                c.setPosition(0)
                self.display.setTextCursor(c)
        else:
            self.play_action.setChecked(True)
        self.stop_action.setEnabled(state in (QTextToSpeech.State.Speaking, QTextToSpeech.State.Synthesizing, QTextToSpeech.State.Paused))
        if self.tts.state is QTextToSpeech.State.Paused:
            self.play_action.setText('Resume')
        elif self.tts.state is QTextToSpeech.State.Speaking:
            self.play_action.setText('Pause')
        else:
            self.play_action.setText('Play')

    def toggled(self):
        if self.tts.state is QTextToSpeech.State.Paused:
            self.tts.resume()
        elif self.tts.state is QTextToSpeech.State.Speaking:
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
