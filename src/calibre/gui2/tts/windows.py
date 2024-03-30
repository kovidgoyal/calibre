#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from calibre.utils.windows.winspeech import Error, MarkReached, MediaState, MediaStateChanged, WinSpeech

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
                if chunk:
                    if isinstance(chunk[-1], int):
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


def chunk_has_text(chunk):
    for x in chunk:
        if isinstance(x, str) and x:
            return True
    return False


class Client:

    mark_template = ''
    name = 'winspeech'
    min_rate = 0.5
    max_rate = 6.0
    default_system_rate = 1.0
    chunk_size = 64 * 1024

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
        self.default_system_audio_device = self.backend.get_audio_device().device
        self.default_system_voice = self.backend.default_voice().voice
        self.apply_settings()

    def get_all_voices(self):
        return self.backend.all_voices().voices

    def get_all_audio_devices(self):
        return self.backend.all_audio_devices().devices

    def __del__(self):
        if self.backend is not None:
            self.backend.shutdown()
            self.backend = None
    shutdown = __del__

    def dispatch_msg(self, msg):
        self.dispatch_on_main_thread(partial(self.handle_event, msg))

    def speak_current_chunk(self):
        chunk = self.current_chunks[self.current_chunk_idx]
        if chunk_has_text(chunk):
            self.backend.speak(chunk, is_cued=True)
        else:
            self.handle_end_event()

    def handle_end_event(self):
        if self.current_chunk_idx >= len(self.current_chunks) - 1:
            self.clear_chunks()
            self.callback_ignoring_errors(Event(EventType.end))
        else:
            self.current_chunk_idx += 1
            self.speak_current_chunk()

    def handle_event(self, x):
        if isinstance(x, MarkReached):
            if self.current_chunks:
                self.last_mark = x.id
                self.callback_ignoring_errors(Event(EventType.mark, x.id))
        elif isinstance(x, MediaStateChanged):
            if self.current_chunks:
                if x.state is MediaState.ended:
                    self.handle_end_event()
                elif x.state is MediaState.failed:
                    self.clear_chunks()
                    self.callback_ignoring_errors(Event(EventType.cancel))
                    e = x.as_exception()
                    e.display_to_user = True
                    raise e
                elif x.state is MediaState.opened:
                    self.callback_ignoring_errors(Event(EventType.resume if self.next_start_is_resume else EventType.begin))
                    self.next_start_is_resume = False
        elif isinstance(x, Error):
            raise x.as_exception(check_for_no_audio_devices=True)
        else:
            raise KeyError(f'Unknown event type: {x}')

    def speak_simple_text(self, text):
        self.backend.pause()
        self.clear_chunks()
        self.current_callback = None
        if text:
            self.backend.speak(text)

    def speak_marked_text(self, text, callback):
        self.backend.pause()
        self.clear_chunks()
        self.current_callback = callback
        self.current_chunks = tuple(split_into_chunks(text, self.chunk_size))
        self.current_chunk_idx = -100
        if self.current_chunks:
            self.current_chunk_idx = 0
            self.speak_current_chunk()
            self.synthesizing = True

    def callback_ignoring_errors(self, ev):
        if self.current_callback is not None:
            try:
                self.current_callback(ev)
            except Exception:
                import traceback
                traceback.print_exc()

    def clear_chunks(self):
        self.synthesizing = False
        self.next_start_is_resume = False
        self.current_chunk_idx = -100
        self.current_chunks = ()
        self.last_mark = -1

    def stop(self):
        self.backend.pause()
        self.synthesizing = False
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
        was_synthesizing = self.synthesizing
        if self.synthesizing:
            self.pause()
        if new_settings is not None:
            self.settings = new_settings
        try:
            self.backend.set_voice(self.settings.get('voice'), self.default_system_voice)
        except OSError:
            import traceback
            traceback.print_exc()
            self.settings.pop('voice', None)
        try:
            self.backend.set_rate(self.settings.get('rate', self.default_system_rate))
        except OSError:
            import traceback
            traceback.print_exc()
            self.settings.pop('rate', None)
        try:
            self.backend.set_audio_device(self.settings.get('sound_output'), self.default_system_audio_device)
        except OSError:
            import traceback
            traceback.print_exc()
            self.settings.pop('sound_output', None)
        if was_synthesizing:
            self.resume_after_configure()

    def config_widget(self, backend_settings, parent):
        from calibre.gui2.tts.windows_config import Widget
        return Widget(self, backend_settings, parent)

    def chunks_from_last_mark(self):
        if self.last_mark > -1:
            for i, chunk in enumerate(self.current_chunks):
                for ci, x in enumerate(chunk):
                    if x == self.last_mark:
                        chunks = self.current_chunks[i:]
                        chunk = chunk[ci + 1:]
                        if chunk:
                            chunks = (chunk,) + chunks[1:]
                        else:
                            chunks = chunks[1:]
                        return chunks
        return ()

    def resume_after_configure(self):
        self.current_chunks = self.chunks_from_last_mark()
        self.current_chunk_idx = -100
        self.last_mark = -1
        self.next_start_is_resume = True
        self.synthesizing = bool(self.current_chunks)
        if self.synthesizing:
            self.current_chunk_idx = 0
            self.speak_current_chunk()

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
            self.apply_settings()
            return self.settings
