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
        self.current_marked_text = None
        self.last_mark = None
        self.next_cancel_is_for_pause = False
        self.next_begin_is_for_resume = False
        self.current_callback = None

    def create_ssip_client(self):
        from speechd.client import Priority, SpawnError, SSIPClient
        try:
            self.ssip_client = SSIPClient('calibre')
        except SpawnError as err:
            raise TTSSystemUnavailable(_('Could not find speech-dispatcher on your system. Please install it.'), str(err))
        self.ssip_client.set_priority(Priority.TEXT)

    def __del__(self):
        if hasattr(self, 'ssip_client'):
            self.ssip_client.cancel()
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
        self.stop()
        self.set_use_ssml(False)
        self.current_marked_text = self.last_mark = None

        def callback(callback_type, index_mark=None):
            self.dispatch_on_main_thread(partial(self.update_status, callback_type, index_mark))

        self.ssip_client.speak(text, callback)

    def update_status(self, callback_type, index_mark=None):
        from speechd.client import CallbackType
        event = None
        if callback_type is CallbackType.INDEX_MARK:
            self.last_mark = index_mark
            event = Event(EventType.mark, index_mark)
        elif callback_type is CallbackType.BEGIN:
            self.status = {'synthesizing': True, 'paused': False}
            event = Event(EventType.resume if self.next_begin_is_for_resume else EventType.begin)
            self.next_begin_is_for_resume = False
        elif callback_type is CallbackType.END:
            self.status = {'synthesizing': False, 'paused': False}
            event = Event(EventType.end)
        elif callback_type is CallbackType.CANCEL:
            if self.next_cancel_is_for_pause:
                self.status = {'synthesizing': True, 'paused': True}
                event = Event(EventType.pause)
            else:
                self.status = {'synthesizing': False, 'paused': False}
                event = Event(EventType.cancel)
            self.next_cancel_is_for_pause = False
        return event

    def speak_marked_text(self, text, callback):
        self.stop()
        self.current_marked_text = text
        self.last_mark = None

        def callback_wrapper(callback_type, index_mark=None):
            event = self.update_status(callback_type, index_mark)
            if event is not None:
                try:
                    callback(event)
                except Exception:
                    import traceback
                    traceback.print_exc()

        def cw(callback_type, index_mark=None):
            self.dispatch_on_main_thread(partial(callback_wrapper, callback_type, index_mark))
        self.current_callback = cw

        self.set_use_ssml(True)
        self.ssip_client.speak(text, callback=self.current_callback)

    def pause(self):
        if self.status['synthesizing'] and not self.status['paused']:
            self.next_cancel_is_for_pause = True
            self.ssip_client.stop()

    def resume(self):
        if self.current_marked_text is None or not self.status['synthesizing'] or not self.status['paused']:
            return
        self.next_begin_is_for_resume = True
        if self.last_mark is None:
            text = self.current_marked_text
        else:
            mark = self.mark_template.format(self.last_mark)
            idx = self.current_marked_text.find(mark)
            if idx == -1:
                text = self.current_marked_text
            else:
                text = self.current_marked_text[idx:]
        self.ssip_client.speak(text, callback=self.current_callback)

    def stop(self):
        self.current_callback = self.current_marked_text = self.last_mark = None
        self.next_cancel_is_for_pause = False
        self.next_begin_is_for_resume = False
        self.ssip_client.stop()
