#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from .common import Event, EventType


class Client:

    mark_template = '[[sync 0x{:x}]]'

    @classmethod
    def escape_marked_text(cls, text):
        return text.replace('[[', ' [ [ ').replace(']]', ' ] ] ')

    def __init__(self, dispatch_on_main_thread):
        from calibre_extensions.cocoa import NSSpeechSynthesizer
        self.nsss = NSSpeechSynthesizer(self.handle_message)
        self.current_callback = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.status = {'synthesizing': False, 'paused': False}

    def __del__(self):
        self.nsss = None
    shutdown = __del__

    def handle_message(self, message_type, data):
        from calibre_extensions.cocoa import MARK, END
        if message_type == MARK:
            event = Event(EventType.mark, data)
        elif message_type == END:
            event = Event(EventType.end if data else EventType.cancel)
            self.status = {'synthesizing': False, 'paused': False}
        else:
            return
        if self.current_callback is not None:
            try:
                self.current_callback(event)
            except Exception:
                import traceback
                traceback.print_exc()

    def speak_simple_text(self, text):
        self.current_callback = None
        self.nsss.speak(self.escape_marked_text(text))
        self.status = {'synthesizing': True, 'paused': False}

    def speak_marked_text(self, text, callback):
        self.current_callback = callback
        self.nsss.speak(text)
        self.status = {'synthesizing': True, 'paused': False}
        self.current_callback(Event(EventType.begin))

    def pause(self):
        if self.status['synthesizing']:
            self.nsss.pause()
            self.status = {'synthesizing': True, 'paused': True}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.pause))

    def resume(self):
        if self.status['paused']:
            self.nsss.resume()
            self.status = {'synthesizing': True, 'paused': False}
            if self.current_callback is not None:
                self.current_callback(Event(EventType.resume))

    def stop(self):
        self.nsss.stop()
