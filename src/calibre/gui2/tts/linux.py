#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from .common import Event, EventType
from .errors import TTSSystemUnavailable


class Client:

    def __init__(self):
        self.create_ssip_client()

    def create_ssip_client(self):
        from speechd.client import SpawnError, SSIPClient
        try:
            self.ssip_client = SSIPClient('calibre')
        except SpawnError as err:
            raise TTSSystemUnavailable(_('Could not find speech-dispatcher on your system. Please install it.'), str(err))

    def __del__(self):
        self.ssip_client.close()
        del self.ssip_client

    def set_use_ssml(self, on):
        from speechd.client import DataMode, SSIPCommunicationError
        mode = DataMode.SSML if on else DataMode.TEXT
        try:
            self.ssip_client.set_data_mode(mode)
        except SSIPCommunicationError:
            self.ssip_client.close()
            self.create_ssip_client()
            self.ssip_client.set_data_mode(mode)

    def speak_simple_text(self, text):
        self.set_use_ssml(False)
        self.ssip_client.speak(text)

    def speak_marked_text(self, text, callback):
        from speechd.client import CallbackType

        def callback_wrapper(callback_type, index_mark=None):
            if callback_type is CallbackType.INDEX_MARK:
                event = Event(EventType.mark, index_mark)
            elif callback_type is CallbackType.BEGIN:
                event = Event(EventType.begin)
            elif callback_type is CallbackType.END:
                event = Event(EventType.end)
            elif callback_type is CallbackType.CANCEL:
                event = Event(EventType.cancel)
            elif callback_type is CallbackType.PAUSE:
                event = Event(EventType.pause)
            elif callback_type is CallbackType.RESUME:
                event = Event(EventType.resume)
            else:
                return
            callback(event)

        self.set_use_ssml(True)
        self.ssip_client.speak(text, callback=callback_wrapper)
