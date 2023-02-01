#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from time import monotonic
from threading import Thread
from typing import NamedTuple

from calibre import prepare_string_for_xml

from .common import Event, EventType, add_markup


class QueueEntry(NamedTuple):
    stream_number: int
    text: str


class SpeechQueue:

    def __init__(self):
        self.clear()

    def __len__(self):
        return len(self.items)

    def clear(self, keep_mark=False):
        self.items = []
        self.pos = -1
        if not keep_mark:
            self.last_mark = None

    def add(self, stream_number, text):
        self.items.append(QueueEntry(stream_number, text))

    def start(self, stream_number):
        self.pos = -1
        for i, x in enumerate(self.items):
            if x.stream_number == stream_number:
                self.pos = i
                break

    @property
    def is_at_start(self):
        return self.pos == 0

    @property
    def is_at_end(self):
        return self.pos >= len(self.items) - 1

    @property
    def current_stream_number(self):
        if -1 < self.pos < len(self.items):
            return self.items[self.pos].stream_number

    def resume_from_last_mark(self, mark_template):
        if self.pos < 0 or self.pos >= len(self.items):
            return
        item = self.items[self.pos]
        if self.last_mark is None:
            idx = -1
        else:
            idx = item.text.find(mark_template.format(self.last_mark))
        if idx == -1:
            text = item.text
        else:
            text = item.text[idx:]
        yield text
        for i in range(self.pos + 1, len(self.items)):
            yield self.items[i].text


class Client:

    mark_template = '<bookmark mark="{}"/>'
    name = 'sapi'
    min_rate = -10
    max_rate = 10
    chunk_size = 128 * 1024

    @classmethod
    def escape_marked_text(cls, text):
        return prepare_string_for_xml(text)

    def __init__(self, settings=None, dispatch_on_main_thread=lambda f: f()):
        self.create_voice()
        self.ignore_next_stop_event = None
        self.ignore_next_start_event = False
        self.default_system_rate = self.sp_voice.get_current_rate()
        self.default_system_voice = self.sp_voice.get_current_voice()
        self.default_system_sound_output = self.sp_voice.get_current_sound_output()
        self.current_stream_queue = SpeechQueue()
        self.current_callback = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.synthesizing = False
        self.pause_count = 0
        self.settings = settings or {}
        self.apply_settings()

    @property
    def status(self):
        return {'synthesizing': self.synthesizing, 'paused': self.pause_count > 0}

    def clear_pauses(self):
        while self.pause_count:
            self.sp_voice.resume()
            self.pause_count -= 1

    def create_voice(self):
        from calibre.utils.windows.winsapi import ISpVoice
        self.sp_voice = ISpVoice()
        self.events_thread = Thread(name='SAPIEvents', target=self.wait_for_events, daemon=True)
        self.events_thread.start()

    def __del__(self):
        if self.sp_voice is not None:
            self.sp_voice.shutdown_event_loop()
            self.events_thread.join(5)
            self.sp_voice = None
    shutdown = __del__

    def apply_settings(self, new_settings=None):
        if self.pause_count:
            self.clear_pauses()
            self.ignore_next_stop_event = monotonic()
            self.synthesizing = False
        if new_settings is not None:
            self.settings = new_settings
        try:
            self.sp_voice.set_current_rate(self.settings.get('rate', self.default_system_rate))
        except OSError:
            self.settings.pop('rate', None)
        try:
            self.sp_voice.set_current_voice(self.settings.get('voice') or self.default_system_voice)
        except OSError:
            self.settings.pop('voice', None)
        try:
            self.sp_voice.set_current_sound_output(self.settings.get('sound_output') or self.default_system_sound_output)
        except OSError:
            self.settings.pop('sound_output', None)

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
                self.current_stream_queue.last_mark = event_data
                event = Event(EventType.mark, event_data)
            elif event_type == SPEI_START_INPUT_STREAM:
                self.current_stream_queue.start(stream_number)
                if self.ignore_next_start_event:
                    self.ignore_next_start_event = False
                    continue
                self.synthesizing = True
                if not self.current_stream_queue.is_at_start:
                    continue
                event = Event(EventType.begin)
            elif event_type == SPEI_END_INPUT_STREAM:
                if self.ignore_next_stop_event is not None and monotonic() - self.ignore_next_stop_event < 2:
                    self.ignore_next_stop_event = None
                    continue
                self.synthesizing = False
                if not self.current_stream_queue.is_at_end:
                    continue
                event = Event(EventType.end)
            else:
                continue
            if c is not None and stream_number == self.current_stream_queue.current_stream_number:
                try:
                    c(event)
                except Exception:
                    import traceback
                    traceback.print_exc()

    def speak_implementation(self, *args):
        try:
            return self.sp_voice.speak(*args)
        except OSError as err:
            # see https://docs.microsoft.com/en-us/previous-versions/office/developer/speech-technologies/jj127491(v=msdn.10)
            import re
            hr = int(re.search(r'\[hr=(0x\S+)', str(err)).group(1), 16)
            if hr == 0x8004503a:
                raise OSError(_('No active audio output devices found. Connect headphones or speakers.')) from err
            raise

    def speak(self, text, is_xml=False, want_events=True, purge=True):
        from calibre_extensions.winsapi import (
            SPF_ASYNC, SPF_IS_NOT_XML, SPF_PURGEBEFORESPEAK, SPF_IS_XML
        )
        flags = SPF_IS_XML if is_xml else SPF_IS_NOT_XML
        if purge:
            flags |= SPF_PURGEBEFORESPEAK
        return self.speak_implementation(text, flags | SPF_ASYNC, want_events)

    def purge(self):
        from calibre_extensions.winsapi import SPF_PURGEBEFORESPEAK
        self.speak_implementation('', SPF_PURGEBEFORESPEAK, False)
        self.synthesizing = False

    def speak_simple_text(self, text):
        self.current_callback = None
        self.current_stream_queue.clear()
        number = self.speak(text)
        self.clear_pauses()
        self.current_stream_queue.add(number, text)

    def speak_marked_text(self, text, callback):
        self.clear_pauses()
        self.current_stream_queue.clear()
        if self.synthesizing:
            self.ignore_next_stop_event = monotonic()
        self.current_callback = callback
        for i, chunk in enumerate(add_markup(text, self.mark_template, self.escape_marked_text, self.chunk_size)):
            number = self.speak(chunk, is_xml=True, purge=i == 0)
            self.current_stream_queue.add(number, chunk)

    def stop(self):
        self.clear_pauses()
        self.purge()
        if self.current_callback is not None:
            self.current_callback(Event(EventType.cancel))
        self.current_callback = None

    def pause(self):
        self.sp_voice.pause()
        self.pause_count += 1
        if self.current_callback is not None:
            self.current_callback(Event(EventType.pause))

    def resume(self):
        if self.pause_count:
            self.clear_pauses()
            if self.current_callback is not None:
                self.current_callback(Event(EventType.resume))

    def resume_after_configure(self):
        if self.pause_count:
            self.clear_pauses()
            return
        chunks = tuple(self.current_stream_queue.resume_from_last_mark(self.mark_template))
        self.ignore_next_start_event = True
        self.current_stream_queue.clear(keep_mark=True)
        self.purge()
        for chunk in chunks:
            number = self.speak(chunk, is_xml=True, purge=False)
            self.current_stream_queue.add(number, chunk)
        if self.current_callback is not None:
            self.current_callback(Event(EventType.resume))
        self.synthesizing = bool(chunks)

    def get_voice_data(self):
        ans = getattr(self, 'voice_data', None)
        if ans is None:
            ans = self.voice_data = self.sp_voice.get_all_voices()
        return ans

    def get_sound_outputs(self):
        ans = getattr(self, 'sound_outputs', None)
        if ans is None:
            ans = self.sound_outputs = self.sp_voice.get_all_sound_outputs()
        return ans

    def config_widget(self, backend_settings, parent):
        from calibre.gui2.tts.windows_config import Widget
        return Widget(self, backend_settings, parent)

    def change_rate(self, steps=1):
        rate = current_rate = self.settings.get('rate', self.default_system_rate)
        step_size = (self.max_rate - self.min_rate) // 10
        rate += steps * step_size
        rate = max(self.min_rate, min(rate, self.max_rate))
        if rate != current_rate:
            self.settings['rate'] = rate
            was_synthesizing = self.synthesizing
            self.pause()
            self.apply_settings()
            if was_synthesizing:
                self.synthesizing = True
                self.resume_after_configure()
            return self.settings
