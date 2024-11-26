#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import QObject, pyqtSignal


def set_sync_override(allowed):
    from calibre.gui2.viewer.lookup import set_sync_override
    set_sync_override(allowed)


class TTS(QObject):

    event_received = pyqtSignal(object, object)
    settings_changed = pyqtSignal(object)
    configured = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = None

    @property
    def manager(self):
        if self._manager is None:
            from calibre.gui2.tts.manager import TTSManager
            self._manager = TTSManager(self)
            self._manager.saying.connect(self.saying)
            self._manager.state_event.connect(self.state_event)
            self._manager.configured.connect(self.configured)
        return self._manager

    def shutdown(self):
        if self._manager is not None:
            self._manager.stop()
            self._manager = None

    def speak_simple_text(self, text):
        self.manager.speak_simple_text(text)

    def action(self, action, data):
        if action != 'resume_after_configure':  # resume_after_configure is not used in new tts backend
            getattr(self, action)(data)

    def play(self, data):
        set_sync_override(False)
        self.manager.speak_marked_text(data['marked_text'])

    def pause(self, data):
        set_sync_override(True)
        self.manager.pause()

    def resume(self, data):
        set_sync_override(False)
        self.manager.resume()

    def saying(self, first: int, last: int) -> None:
        self.event_received.emit('mark', {'first': first, 'last': last})

    def state_event(self, name: str):
        self.event_received.emit(name, None)

    def stop(self, data):
        set_sync_override(True)
        self.manager.stop()

    def configure(self, data):
        self.manager.configure()

    def slower(self, data):
        self.manager.change_rate(steps=-1)

    def faster(self, data):
        self.manager.change_rate(steps=1)
