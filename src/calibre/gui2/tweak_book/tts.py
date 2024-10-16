#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

import sys

from qt.core import QHBoxLayout, QStackedLayout, QTextBrowser, QVBoxLayout, QWidget

from calibre.gui2.tweak_book.widgets import Dialog


class ConfigWidget(QWidget):

    def __init__(self, parent=None):
        from calibre.gui2.tts.config import EmbeddingConfig
        super().__init__(parent)
        self.h = h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.conf = c = EmbeddingConfig(self)
        h.addWidget(c)
        self.help = q = QTextBrowser(self)
        h.addWidget(q)


class TTSEmbed(Dialog):

    def __init__(self, container, parent=None):
        self.container = container
        super().__init__(_('Add Text-to-speech narration'), 'tts-overlay-dialog', parent=parent)

    def setup_ui(self):
        self.v = v = QVBoxLayout(self)
        self.stack = s = QStackedLayout(self)
        v.addLayout(s)
        v.addWidget(self.bb)


def develop():
    from calibre.ebooks.oeb.polish.container import get_container
    from calibre.gui2 import Application
    path = sys.argv[-1]
    container = get_container(path, tweak_mode=True)
    app = Application([])
    d = TTSEmbed(container)
    d.exec()
    del d
    del app


if __name__ == '__main__':
    develop()
