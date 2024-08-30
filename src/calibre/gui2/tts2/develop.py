#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QAction, QPlainTextEdit, QToolBar

from calibre.gui2 import Application
from calibre.gui2.main_window import MainWindow

TEXT = '''\
Demonstration of DOCX support in calibre

This document demonstrates the ability of the calibre DOCX Input plugin to convert the various typographic features in a Microsoft Word
(2007 and newer) document. Convert this document to a modern ebook format, such as AZW3 for Kindles or EPUB for other ebook readers,
to see it in action.

There is support for images, tables, lists, footnotes, endnotes, links, dropcaps and various types of text and paragraph level formatting.

To see the DOCX conversion in action, simply add this file to calibre using the “Add Books” button and then click “Convert”.
Set the output format in the top right corner of the conversion dialog to EPUB or AZW3 and click “OK”.
'''


def to_marked_text(text=TEXT):
    pos = 0
    for word in text.split():
        yield pos
        yield word
        yield ' '
        pos += 1 + len(word)


class MainWindow(MainWindow):

    def __init__(self, text):
        super().__init__()
        self.display = d = QPlainTextEdit(self)
        self.toolbar = tb = QToolBar(self)
        self.addToolBar(tb)
        self.setCentralWidget(d)
        d.setPlainText(text)
        d.setReadOnly(True)
        self.marked_text = to_marked_text(text)
        self.resize(self.sizeHint())
        self.play_action = pa = QAction('Play')
        pa.setCheckable(True)
        self.toolbar.addAction(pa)
        self.faster_action = fa = QAction('Faster')
        self.toolbar.addAction(fa)
        self.slower_action = sa = QAction('Slower')
        self.toolbar.addAction(sa)
        self.configure_action = ca = QAction('Configure')
        self.toolbar.addAction(ca)


def main():
    app = Application([])
    mw = MainWindow(TEXT)
    mw.set_exception_handler()
    mw.show()
    app.exec()


if __name__ == '__main__':
    main()
