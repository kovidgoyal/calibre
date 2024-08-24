#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QMediaDevices, QObject, QTextToSpeech

from .types import EngineSpecificSettings


class QtTTSBackend(QObject):

    def __init__(self, engine_name: str = '', settings: EngineSpecificSettings = EngineSpecificSettings(), parent: QObject|None = None):
        super().__init__(parent)
        s = {}
        if settings.audio_device_id:
            for x in QMediaDevices.audioOutputs():
                if bytes(x.id) == settings.audio_device_id.id:
                    s['audioDevice'] = x
                    break
        self.tts = QTextToSpeech(engine_name, s, self)
