#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from calibre import prepare_string_for_xml

from .common import Event, EventType
from .errors import TTSSystemUnavailable


class Client:

    mark_template = '<mark name="{}"/>'

    @classmethod
    def escape_marked_text(cls, text):
        return prepare_string_for_xml(text)

    def __init__(self, dispatch_on_main_thread):
        self.create_ssip_client()
        self.status = {'synthesizing': False, 'paused': False}
        self.dispatch_on_main_thread = dispatch_on_main_thread

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

        def callback(callback_type, index_mark=None):
            self.dispatch_on_main_thread(partial(self.update_status, callback_type, index_mark))

        self.ssip_client.speak(text, callback)

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

    def msg_as_event(self, callback_type, index_mark=None):
        from speechd.client import CallbackType
        if callback_type is CallbackType.INDEX_MARK:
            return Event(EventType.mark, index_mark)
        if callback_type is CallbackType.BEGIN:
            return Event(EventType.begin)
        if callback_type is CallbackType.END:
            return Event(EventType.end)
        if callback_type is CallbackType.CANCEL:
            return Event(EventType.cancel)
        if callback_type is CallbackType.PAUSE:
            return Event(EventType.pause)
        if callback_type is CallbackType.RESUME:
            return Event(EventType.resume)

    def speak_marked_text(self, text, callback):

        def callback_wrapper(callback_type, index_mark=None):
            self.update_status(callback_type, index_mark)
            event = self.msg_as_event(callback_type, index_mark)
            if event is not None:
                try:
                    callback(event)
                except Exception:
                    import traceback
                    traceback.print_exc()

        def cw(callback_type, index_mark=None):
            self.dispatch_on_main_thread(partial(callback_wrapper, callback_type, index_mark))

        self.set_use_ssml(True)
        self.ssip_client.speak(text, callback=cw)
