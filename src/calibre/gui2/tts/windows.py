#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from threading import Thread
from .common import Event, EventType


class Client:

    def __init__(self):
        from calibre.utils.windows.winsapi import ISpVoice
        self.sp_voice = ISpVoice()
        self.events_thread = Thread(name='SAPIEvents', target=self.wait_for_events, daemon=True)
        self.events_thread.start()
        self.current_stream_number = None
        self.current_callback = None

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
            c = self.current_callback
            if c is not None:
                c()

    def get_events(self):
        from calibre_extensions.winsapi import SPEI_TTS_BOOKMARK, SPEI_START_INPUT_STREAM, SPEI_END_INPUT_STREAM
        ans = []
        for (stream_number, event_type, event_data) in self.sp_voice.get_events():
            if stream_number == self.current_stream_number:
                if event_type == SPEI_TTS_BOOKMARK:
                    event = Event(EventType.mark, event_data)
                elif event_type == SPEI_START_INPUT_STREAM:
                    event = Event(EventType.begin)
                elif event_type == SPEI_END_INPUT_STREAM:
                    event = Event(EventType.end)
                else:
                    continue
                ans.append(event)
        return ans

    def speak_simple_text(self, text):
        from calibre_extensions.winsapi import SPF_ASYNC, SPF_PURGEBEFORESPEAK, SPF_IS_NOT_XML
        self.current_callback = None
        self.current_stream_number = self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_NOT_XML)

    def speak_marked_text(self, text, callback):
        from calibre_extensions.winsapi import SPF_ASYNC, SPF_PURGEBEFORESPEAK, SPF_IS_XML
        self.current_callback = callback
        self.current_stream_number = self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_XML, True)
