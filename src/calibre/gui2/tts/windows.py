#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from threading import Thread


class Client:

    def __init__(self):
        from calibre.utils.windows.winsapi import ISpVoice
        self.sp_voice = ISpVoice()
        self.events_thread = Thread(name='SAPIEvents', target=self.wait_for_events, daemon=True)
        self.events_thread.start()

    def __del__(self):
        self.sp_voice.shutdown_event_loop()
        self.events_thread.join(5)
        self.sp_voice = None

    def wait_for_events(self):
        self.sp_voice.run_event_loop(self.process_event)

    def process_event(self, stream_number, event_type, event_data=None):
        pass

    def speak_simple_text(self, text):
        from calibre_extensions.winsapi import SPF_ASYNC, SPF_PURGEBEFORESPEAK, SPF_IS_NOT_XML
        self.sp_voice.speak(text, SPF_ASYNC | SPF_PURGEBEFORESPEAK | SPF_IS_NOT_XML)
