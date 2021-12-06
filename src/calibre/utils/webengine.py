#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


import json
from qt.core import QObject, pyqtSignal
from qt.webengine import QWebEngineScript, QWebEngineSettings

from calibre.utils.rapydscript import special_title


def secure_webengine(view_or_page_or_settings, for_viewer=False):
    s = view_or_page_or_settings.settings() if hasattr(
        view_or_page_or_settings, 'settings') else view_or_page_or_settings
    a = s.setAttribute
    a(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    if not for_viewer:
        a(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        s.setUnknownUrlSchemePolicy(QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes)
        if hasattr(view_or_page_or_settings, 'setAudioMuted'):
            view_or_page_or_settings.setAudioMuted(True)
    a(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    a(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    # ensure javascript cannot read from local files
    a(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    a(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, False)
    return s


def insert_scripts(profile, *scripts):
    sc = profile.scripts()
    for script in scripts:
        for existing in sc.find(script.name()):
            sc.remove(existing)
    for script in scripts:
        sc.insert(script)


def create_script(
    name, src, world=QWebEngineScript.ScriptWorldId.ApplicationWorld,
    injection_point=QWebEngineScript.InjectionPoint.DocumentReady,
    on_subframes=True
):
    script = QWebEngineScript()
    if isinstance(src, bytes):
        src = src.decode('utf-8')
    script.setSourceCode(src)
    script.setName(name)
    script.setWorldId(world)
    script.setInjectionPoint(injection_point)
    script.setRunsOnSubFrames(on_subframes)
    return script


from_js = pyqtSignal


class to_js(str):

    def __call__(self, *a):
        print(f'WARNING: Calling {self.name}() before the javascript bridge is ready')
    emit = __call__


class to_js_bound(QObject):

    def __init__(self, bridge, name):
        QObject.__init__(self, bridge)
        self.name = name

    def __call__(self, *args):
        self.parent().page.runJavaScript('if (window.python_comm) python_comm._from_python({}, {})'.format(
            json.dumps(self.name), json.dumps(args)), QWebEngineScript.ScriptWorldId.ApplicationWorld)
    emit = __call__


class Bridge(QObject):

    bridge_ready = pyqtSignal()

    def __init__(self, page):
        QObject.__init__(self, page)
        self._signals = json.dumps(tuple({k for k, v in self.__class__.__dict__.items() if isinstance(v, pyqtSignal)}))
        self._signals_registered = False
        page.titleChanged.connect(self._title_changed)
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, to_js):
                v.name = k

    @property
    def page(self):
        return self.parent()

    @property
    def ready(self):
        return self._signals_registered

    def _title_changed(self, title):
        if title.startswith(special_title):
            self._poll_for_messages()

    def _register_signals(self):
        self._signals_registered = True
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, to_js):
                setattr(self, k, to_js_bound(self, k))
        self.page.runJavaScript('python_comm._register_signals(' + self._signals + ')', QWebEngineScript.ScriptWorldId.ApplicationWorld)
        self.bridge_ready.emit()

    def _poll_for_messages(self):
        self.page.runJavaScript('python_comm._poll()', QWebEngineScript.ScriptWorldId.ApplicationWorld, self._dispatch_messages)

    def _dispatch_messages(self, messages):
        try:
            for msg in messages:
                if isinstance(msg, dict):
                    mt = msg.get('type')
                    if mt == 'signal':
                        signal = getattr(self, msg['name'], None)
                        if signal is None:
                            print('WARNING: No js-to-python signal named: ' + msg['name'])
                        else:
                            args = msg['args']
                            if args:
                                signal.emit(*args)
                            else:
                                signal.emit()
                    elif mt == 'qt-ready':
                        self._register_signals()
        except Exception:
            if messages:
                import traceback
                traceback.print_exc()
