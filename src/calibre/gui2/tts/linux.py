#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from calibre import prepare_string_for_xml

from .common import Event, EventType
from .errors import TTSSystemUnavailable


class Client:

    mark_template = '<mark name="{}"/>'

    @classmethod
    def escape_marked_text(cls, text):
        return prepare_string_for_xml(text)

    def __init__(self):
        self.create_ssip_client()
        self.pending_events = []
        self.status = {'synthesizing': False, 'paused': False}

    def create_ssip_client(self):
        from speechd.client import SpawnError, SSIPClient
        try:
            self.ssip_client = SSIPClient('calibre')
        except SpawnError as err:
            raise TTSSystemUnavailable(_('Could not find speech-dispatcher on your system. Please install it.'), str(err))

    def __del__(self):
        if hasattr(self, 'ssip_client'):
            self.ssip_client.close()
            del self.ssip_client
    shutdown = __del__

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
        self.pending_events = []
        self.ssip_client.speak(text, self.update_status)

    def update_status(self, callback_type, index_mark=None):
        from speechd.client import CallbackType
        if callback_type is CallbackType.BEGIN:
            self.status = {'synthesizing': True, 'paused': False}
        elif callback_type is CallbackType.END:
            self.status = {'synthesizing': False, 'paused': False}
        elif callback_type is CallbackType.CANCEL:
            self.status = {'synthesizing': False, 'paused': False}
        elif callback_type is CallbackType.PAUSE:
            self.status = {'synthesizing': True, 'paused': True}
        elif callback_type is CallbackType.RESUME:
            self.status = {'synthesizing': True, 'paused': False}

    def speak_marked_text(self, text, callback):
        from speechd.client import CallbackType

        def callback_wrapper(callback_type, index_mark=None):
            self.update_status(callback_type, index_mark)
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
            self.pending_events.append(event)
            callback()

        self.set_use_ssml(True)
        self.pending_events = []
        self.ssip_client.speak(text, callback=callback_wrapper)

    def get_events(self):
        events = self.pending_events
        self.pending_events = []
        return events
