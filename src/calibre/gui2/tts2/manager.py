#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QObject


class TTSManager(QObject):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts = None

    @property
    def tts(self):
        if self._tts is None:
            from calibre.gui2.tts.types import create_tts_backend
            self._tts = create_tts_backend(parent=self)
        return self._tts

    def speak_marked_text(self, marked_text):
        pass
