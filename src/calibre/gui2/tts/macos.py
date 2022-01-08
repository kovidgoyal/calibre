#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from .common import Event, EventType, add_markup


class Client:

    mark_template = '[[sync 0x{:x}]]'
    END_MARK = 0xffffffff
    name = 'nsss'
    min_rate = 10
    max_rate = 340
    chunk_size = 0

    @classmethod
    def escape_marked_text(cls, text):
        return text.replace('[[', ' [ [ ').replace(']]', ' ] ] ')

    def __init__(self, settings=None, dispatch_on_main_thread=lambda f: f()):
        from calibre_extensions.cocoa import NSSpeechSynthesizer
        self.nsss = NSSpeechSynthesizer(self.handle_message)
        self.default_system_rate = self.nsss.get_current_rate()
        self.default_system_voice = self.nsss.get_current_voice()
        self.current_callback = None
        self.current_marked_text = self.last_mark = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.status = {'synthesizing': False, 'paused': False}
        self.settings = settings or {}
        self.ignore_next_stop_event = False
        self.apply_settings()

    def apply_settings(self, new_settings=None):
        if self.status['paused']:
            self.nsss.resume()
            self.ignore_next_stop_event = True
            self.status = {'synthesizing': False, 'paused': False}
        if new_settings is not None:
            self.settings = new_settings
        self.nsss.set_current_voice(self.settings.get('voice') or self.default_system_voice)
        rate = self.settings.get('rate', self.default_system_rate)
        self.nsss.set_current_rate(rate)

    def __del__(self):
        self.nsss = None
    shutdown = __del__

    def handle_message(self, message_type, data):
        from calibre_extensions.cocoa import MARK, END
        event = None
        if message_type == MARK:
            self.last_mark = data
            event = Event(EventType.mark, data)
        elif message_type == END:
            if self.ignore_next_stop_event:
                self.ignore_next_stop_event = False
                return
            event = Event(EventType.end if data else EventType.cancel)
            self.status = {'synthesizing': False, 'paused': False}
        if event is not None and self.current_callback is not None:
            try:
                self.current_callback(event)
            except Exception:
                import traceback
                traceback.print_exc()

    def speak_simple_text(self, text):
        self.current_callback = None
        self.current_marked_text = self.last_mark = None
        self.nsss.speak(self.escape_marked_text(text))
        self.status = {'synthesizing': True, 'paused': False}

    def speak_marked_text(self, marked_text, callback):
        text = ''.join(add_markup(marked_text, self.mark_template, self.escape_marked_text, self.chunk_size))
        self.current_callback = callback
        self.current_marked_text = text
        self.last_mark = None
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

    def resume_after_configure(self):
        if self.status['paused']:
            self.resume()
            return
        if self.last_mark is None:
            idx = -1
        else:
            mark = self.mark_template.format(self.last_mark)
            idx = self.current_marked_text.find(mark)
        if idx == -1:
            text = self.current_marked_text
        else:
            text = self.current_marked_text[idx:]
        self.nsss.speak(text)
        self.status = {'synthesizing': True, 'paused': False}
        if self.current_callback is not None:
            self.current_callback(Event(EventType.resume))

    def stop(self):
        self.nsss.stop()

    @property
    def rate(self):
        return self.nss.get_current_rate()

    @rate.setter
    def rate(self, val):
        val = val or self.default_system_rate
        self.nss.set_current_rate(float(val))

    def get_voice_data(self):
        ans = getattr(self, 'voice_data', None)
        if ans is None:
            ans = self.voice_data = self.nsss.get_all_voices()
        return ans

    def config_widget(self, backend_settings, parent):
        from calibre.gui2.tts.macos_config import Widget
        return Widget(self, backend_settings, parent)

    def change_rate(self, steps=1):
        rate = current_rate = self.settings.get('rate', self.default_system_rate)
        step_size = (self.max_rate - self.min_rate) // 10
        rate += steps * step_size
        rate = max(self.min_rate, min(rate, self.max_rate))
        if rate != current_rate:
            self.settings['rate'] = rate
            prev_state = self.status.copy()
            self.pause()
            self.apply_settings()
            if prev_state['synthesizing']:
                self.status = {'synthesizing': True, 'paused': False}
                self.resume_after_configure()
            return self.settings
