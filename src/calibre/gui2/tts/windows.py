#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from calibre.utils.windows.winspeech import WinSpeech, Error, MarkReached, MediaStateChanged, MediaState

from .common import Event, EventType

def split_into_chunks(marked_text, chunk_size):
    chunk = []
    tlen = 0
    for x in marked_text:
        if isinstance(x, int):
            chunk.append(x)
        else:
            sz = len(x)
            if tlen + sz > chunk_size:
                mark = None
                if chunk and isinstance(chunk[-1], int):
                    mark = chunk[-1]
                    del chunk[-1]
                    yield chunk
                chunk = [] if mark is None else [mark]
                tlen = sz
                chunk.append(x)
            else:
                chunk.append(x)
                tlen += sz
    if chunk:
        yield chunk


class Client:

    mark_template = ''
    name = 'winspeech'
    min_rate = 0.5
    max_rate = 6.0
    default_system_rate = 1.0
    chunk_size = 128 * 1024

    @classmethod
    def escape_marked_text(cls, text):
        return text

    def __init__(self, settings=None, dispatch_on_main_thread=lambda f: f()):
        self.backend = WinSpeech(self.dispatch_msg)
        self.last_mark = -1
        self.current_callback = None
        self.dispatch_on_main_thread = dispatch_on_main_thread
        self.synthesizing = False
        self.settings = settings or {}
        self.clear_chunks()
        self.apply_settings()

    def __del__(self):
        if self.backend is not None:
            self.backend.shutdown()
            self.backend = None
    shutdown = __del__

    def dispatch_msg(self, msg):
        self.dispatch_on_main_thread(partial(self.handle_event, msg))

    def handle_event(self, x):
        if isinstance(x, MarkReached) and self.current_chunks:
            self.last_mark = x.id
            self.callback_ignoring_errors(Event(EventType.mark, x.id))
        elif isinstance(x, MediaStateChanged) and self.current_chunks:
            if x.state is MediaState.ended:
                if self.current_chunk_idx >= len(self.current_chunks) - 1:
                    self.clear_chunks()
                    self.callback_ignoring_errors(Event(EventType.end))
                else:
                    self.current_chunk_idx += 1
                    self.backend.speak(self.current_chunks[self.current_chunk_idx], is_cued=True)
            elif x.state is MediaState.failed:
                raise x.as_exception()
        elif isinstance(x, Error):
            raise x.as_exception(check_for_no_audio_devices=True)
        else:
            raise KeyError(f'Unknown event type: {x}')

    def speak_simple_text(self, text):
        self.current_callback = None
        self.clear_chunks()
        self.backend.speak(text)

    def speak_marked_text(self, text, callback):
        self.backend.pause()
        self.clear_chunks()
        self.current_callback = callback
        self.current_chunks = tuple(split_into_chunks(text, self.chunk_size))
        self.current_chunk_idx = 0
        if self.current_chunks:
            self.backend.speak(self.current_chunks[self.current_chunk_idx], is_cued=True)
            self.synthesizing = True
            if self.current_callback is not None:
                self.current_callback(Event(EventType.begin))

    def callback_ignoring_errors(self, ev):
        if self.current_callback is not None:
            try:
                self.current_callback(ev)
            except Exception:
                import traceback
                traceback.print_exc()

    def clear_chunks(self):
        self.synthesizing = False
        self.current_chunk_idx = -100
        self.current_chunks = []
        self.last_mark = -1

    def stop(self):
        self.backend.pause()
        self.clear_chunks()
        if self.current_callback is not None:
            self.current_callback(Event(EventType.cancel))

    def pause(self):
        self.backend.pause()
        self.synthesizing = False
        if self.current_callback is not None:
            self.current_callback(Event(EventType.pause))

    def resume(self):
        self.backend.play()
        self.synthesizing = True
        if self.current_callback is not None:
            self.current_callback(Event(EventType.resume))

    def apply_settings(self, new_settings=None):
        pass

    def config_widget(self, backend_settings, parent):
        from calibre.gui2.tts.windows_config import Widget
        return Widget(self, backend_settings, parent)

    def change_rate(self, steps=1):
        rate = current_rate = self.settings.get('rate', self.default_system_rate)
        if rate < 1:
            step_size = 0.1
        else:
            step_size = 0.5
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
