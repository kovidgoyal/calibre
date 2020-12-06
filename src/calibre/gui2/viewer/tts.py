#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from PyQt5.Qt import QObject, QVBoxLayout, pyqtSignal

from calibre.gui2 import error_dialog
from calibre.gui2.viewer.config import get_pref_group, vprefs
from calibre.gui2.widgets2 import Dialog


class Config(Dialog):

    def __init__(self, tts_client, ui_settings, backend_settings, parent):
        self.tts_client = tts_client
        self.ui_settings = ui_settings
        self.backend_settings = backend_settings
        Dialog.__init__(self, _('Configure Read aloud'), 'read-aloud-config', parent, prefs=vprefs)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.config_widget = self.tts_client.config_widget(self.backend_settings, self)
        l.addWidget(self.config_widget)
        l.addWidget(self.bb)

    def accept(self):
        self.backend_settings = self.config_widget.backend_settings
        return super().accept()


def add_markup(text_parts):
    from calibre.gui2.tts.implementation import Client
    buf = []
    bm = Client.mark_template
    for x in text_parts:
        if isinstance(x, int):
            buf.append(bm.format(x))
        else:
            buf.append(Client.escape_marked_text(x))
    return ''.join(buf)


class TTS(QObject):

    dispatch_on_main_thread_signal = pyqtSignal(object)
    event_received = pyqtSignal(object, object)
    settings_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._tts_client = None
        self.dispatch_on_main_thread_signal.connect(self.dispatch_on_main_thread)

    def dispatch_on_main_thread(self, func):
        try:
            func()
        except Exception:
            import traceback
            traceback.print_exc()

    @property
    def tts_client(self):
        if self._tts_client is None:
            from calibre.gui2.tts.implementation import Client
            self._tts_client = Client(self.dispatch_on_main_thread_signal.emit)
        return self._tts_client

    def shutdown(self):
        if self._tts_client is not None:
            self._tts_client.shutdown()
            self._tts_client = None

    def speak_simple_text(self, text):
        from calibre.gui2.tts.errors import TTSSystemUnavailable
        try:
            self.tts_client.speak_simple_text(text)
        except TTSSystemUnavailable as err:
            return error_dialog(self.parent(), _('Text-to-Speech unavailable'), str(err), show=True)

    def action(self, action, data):
        from calibre.gui2.tts.errors import TTSSystemUnavailable
        try:
            getattr(self, action)(data)
        except TTSSystemUnavailable as err:
            return error_dialog(self.parent(), _('Text-to-Speech unavailable'), str(err), show=True)

    def play(self, data):
        marked_text = add_markup(data['marked_text'])
        self.tts_client.speak_marked_text(marked_text, self.callback)

    def pause(self, data):
        self.tts_client.pause()

    def resume(self, data):
        self.tts_client.resume()

    def callback(self, event):
        data = event.data
        if event.type is event.type.mark:
            data = int(data)
        self.event_received.emit(event.type.name, data)

    def stop(self, data):
        self.tts_client.stop()

    def configure(self, data):
        ui_settings = get_pref_group('tts').copy()
        key = 'tts_' + self.tts_client.name
        d = Config(self.tts_client, ui_settings, vprefs.get(key) or {}, parent=self.parent())
        if d.exec_() == d.DialogCode.Accepted:
            vprefs[key] = d.backend_settings
            self.settings_changed.emit(d.ui_settings)
