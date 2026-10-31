#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
from typing import TYPE_CHECKING

from qt.core import QBuffer, QIODevice, QObject, QUrl, pyqtSignal, sip
from qt.webengine import QWebEngineProfile, QWebEngineScript, QWebEngineSettings, QWebEngineUrlScheme

from calibre.constants import FAKE_PROTOCOL, SPECIAL_TITLE_FOR_WEBENGINE_COMMS, cache_dir

if TYPE_CHECKING:
    from qt.webengine import QWebEnginePage, QWebEngineScriptCollection, QWebEngineUrlRequestJob, QWebEngineView


def setup_fake_protocol() -> None:
    p = FAKE_PROTOCOL.encode('ascii')
    if not QWebEngineUrlScheme.schemeByName(p).name():
        scheme = QWebEngineUrlScheme(p)
        scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
        scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme)
        QWebEngineUrlScheme.registerScheme(scheme)


def setup_profile(profile: QWebEngineProfile | None) -> QWebEngineProfile:
    # Qt uses persistent storage path to store cached GPU data even for OTR profiles
    base = os.path.abspath(os.path.join(cache_dir(), 'qwe', profile.storageName() or 'dp'))  # ty: ignore[unresolved-attribute]
    cp = os.path.join(base, 'c')
    if profile.cachePath() != cp:  # ty: ignore[unresolved-attribute]
        profile.setCachePath(cp)  # ty: ignore[unresolved-attribute]
    sp = os.path.join(base, 'sp')
    if profile.persistentStoragePath() != sp:  # ty: ignore[unresolved-attribute]
        profile.setPersistentStoragePath(sp)  # ty: ignore[unresolved-attribute]
    return profile  # ty: ignore[invalid-return-type]


def setup_default_profile() -> QWebEngineProfile:
    return setup_profile(QWebEngineProfile.defaultProfile())


def send_reply(rq: QWebEngineUrlRequestJob, mime_type: str, data: bytes) -> None:
    if sip.isdeleted(rq):
        return
    # make the buf a child of rq so that it is automatically deleted when
    # rq is deleted
    buf = QBuffer(parent=rq)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    # we have to copy data into buf as it will be garbage
    # collected by python
    buf.write(data)
    buf.seek(0)
    buf.close()
    rq.reply(mime_type.encode('ascii'), buf)


def secure_webengine(view_or_page_or_settings: QWebEngineView | QWebEnginePage | QWebEngineSettings | None, for_viewer: bool = False) -> QWebEngineSettings:
    s: QWebEngineSettings = view_or_page_or_settings.settings() if hasattr(view_or_page_or_settings, 'settings') else view_or_page_or_settings  # ty: ignore[call-non-callable, invalid-assignment]
    a = s.setAttribute
    a(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    if not for_viewer:
        a(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        s.setUnknownUrlSchemePolicy(QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes)
        if hasattr(view_or_page_or_settings, 'setAudioMuted'):
            view_or_page_or_settings.setAudioMuted(True)  # ty: ignore[call-non-callable]
    a(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    a(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    # ensure javascript cannot read from local files
    a(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    a(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, False)
    return s


def insert_scripts(profile: QWebEngineProfile, *scripts: QWebEngineScript) -> None:
    sc: QWebEngineScriptCollection = profile.scripts()  # ty: ignore[invalid-assignment]
    for script in scripts:
        for existing in sc.find(script.name()):
            sc.remove(existing)
    for script in scripts:
        sc.insert(script)


def create_script(
    name: str,
    src: str | bytes = '',
    world: int = QWebEngineScript.ScriptWorldId.ApplicationWorld,
    injection_point: QWebEngineScript.InjectionPoint = QWebEngineScript.InjectionPoint.DocumentReady,
    on_subframes: bool = True,
    path: str = '',
) -> QWebEngineScript:
    script = QWebEngineScript()
    if path:
        script.setSourceUrl(QUrl.fromLocalFile(path))
    else:
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
    def __call__(self, *a: object) -> None:
        print(f'WARNING: Calling {self}() before the javascript bridge is ready')

    emit = __call__


class to_js_bound(QObject):
    def __init__(self, bridge: Bridge, name: str) -> None:
        QObject.__init__(self, bridge)
        self.name = name

    def __call__(self, *args: object) -> None:
        bridge = self.parent()
        assert isinstance(bridge, Bridge)
        bridge.page.runJavaScript(
            f'if (window.python_comm) python_comm._from_python({json.dumps(self.name)}, {json.dumps(args)})',
            QWebEngineScript.ScriptWorldId.ApplicationWorld,
        )

    emit = __call__


class Bridge(QObject):
    bridge_ready = pyqtSignal()

    def __init__(self, page: QWebEnginePage) -> None:
        QObject.__init__(self, page)
        self._signals = json.dumps(tuple({k for k, v in self.__class__.__dict__.items() if isinstance(v, pyqtSignal)}))
        self._signals_registered = False
        page.titleChanged.connect(self._title_changed)
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, to_js):
                v.name = k

    @property
    def page(self) -> QWebEnginePage:
        return self.parent()  # ty: ignore[invalid-return-type]

    @property
    def ready(self) -> bool:
        return self._signals_registered

    def _title_changed(self, title: str) -> None:
        if title.startswith(SPECIAL_TITLE_FOR_WEBENGINE_COMMS):
            self._poll_for_messages()

    def _register_signals(self) -> None:
        self._signals_registered = True
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, to_js):
                setattr(self, k, to_js_bound(self, k))
        self.page.runJavaScript('python_comm._register_signals(' + self._signals + ')', QWebEngineScript.ScriptWorldId.ApplicationWorld)
        self.bridge_ready.emit()

    def _poll_for_messages(self) -> None:
        self.page.runJavaScript('python_comm._poll()', QWebEngineScript.ScriptWorldId.ApplicationWorld, self._dispatch_messages)

    def _dispatch_messages(self, messages: list[object]) -> None:
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
