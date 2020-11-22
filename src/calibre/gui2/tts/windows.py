#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from threading import Thread

from calibre import prepare_string_for_xml

from .common import Event, EventType


class Client:

    mark_template = '<bookmark mark="{}"/>'

    @classmethod
    def escape_marked_text(cls, text):
        return prepare_string_for_xml(text)

    def __init__(self, dispatch_on_main_thread):
        from calibre.utils.windows.winsapi import ISpVoice
        self.sp_voice = ISpVoice()
        self.events_thread = Thread(name='SAPIEvents', target=self.wait_for_events, daemon=True)
        self.events_thread.start()
        self.current_stream_number = None
        self.current_callback = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.status = {'synthesizing': False, 'paused': False}

    def __del__(self):
        if self.sp_voice is not None:
            self.sp_voice.shutdown_event_loop()
            self.events_thread.join(5)
            self.sp_voice = None
    shutdown = __del__

    def wait_for_events(self):
        while True:
            if self.sp_voice.wait_for_event() is False:
                break
            self.dispatch_on_main_thread(self.handle_events)

    def handle_events(self):
        from calibre_extensions.winsapi import (
            SPEI_END_INPUT_STREAM, SPEI_START_INPUT_STREAM, SPEI_TTS_BOOKMARK
        )
        c = self.current_callback
        for (stream_number, event_type, event_data) in self.sp_voice.get_events():
            if event_type == SPEI_TTS_BOOKMARK:
                event = Event(EventType.mark, event_data)
            elif event_type == SPEI_START_INPUT_STREAM:
                event = Event(EventType.begin)
                self.status = {'synthesizing': True, 'paused': False}
            elif event_type == SPEI_END_INPUT_STREAM:
                event = Event(EventType.end)
                self.status = {'synthesizing': False, 'paused': False}
            else:
                continue
            if c is not None and stream_number == self.current_stream_number:
                try:
                    c(event)
                except Exception:
                    import traceback
                    traceback.print_exc()

    def speak_simple_text(self, text):
        from calibre_extensions.winsapi import (
            SPF_ASYNC, SPF_IS_NOT_XML, SPF_PURGEBEFORESPEAK
        )
        self.current_callback = None
        self.current_stream_number = self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_NOT_XML, True)

    def speak_marked_text(self, text, callback):
        from calibre_extensions.winsapi import (
            SPF_ASYNC, SPF_IS_XML, SPF_PURGEBEFORESPEAK
        )
        self.current_callback = callback
        self.current_stream_number = self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_XML, True)

    def stop(self):
        from calibre_extensions.winsapi import SPF_PURGEBEFORESPEAK
        if self.status['paused']:
            self.sp_voice.resume()
        self.sp_voice.speak('', SPF_PURGEBEFORESPEAK, False)
        self.status = {'synthesizing': False, 'paused': False}
        if self.current_callback is not None:
            self.current_callback(Event(EventType.cancel))
        self.current_callback = None

    def pause(self):
        if self.status['synthesizing'] and not self.status['paused']:
            self.sp_voice.pause()
            self.status = {'synthesizing': True, 'paused': True}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.pause))

    def resume(self):
        if self.status['paused']:
            self.sp_voice.resume()
            self.status = {'synthesizing': True, 'paused': False}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.resume))
