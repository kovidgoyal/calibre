#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from PyQt5.QtWebEngineWidgets import QWebEngineScript


def secure_webengine(view_or_page_or_settings, for_viewer=False):
    s = view_or_page_or_settings.settings() if hasattr(
        view_or_page_or_settings, 'settings') else view_or_page_or_settings
    a = s.setAttribute
    a(s.PluginsEnabled, False)
    if not for_viewer:
        a(s.JavascriptEnabled, False)
        s.setUnknownUrlSchemePolicy(s.DisallowUnknownUrlSchemes)
    a(s.JavascriptCanOpenWindows, False)
    a(s.JavascriptCanAccessClipboard, False)
    # ensure javascript cannot read from local files
    a(s.LocalContentCanAccessFileUrls, False)
    a(s.AllowWindowActivationFromJavaScript, False)
    return s


def insert_scripts(profile, *scripts):
    sc = profile.scripts()
    for script in scripts:
        for existing in sc.findScripts(script.name()):
            sc.remove(existing)
    for script in scripts:
        sc.insert(script)


def create_script(name, src, world=QWebEngineScript.ApplicationWorld, injection_point=QWebEngineScript.DocumentReady, on_subframes=True):
    script = QWebEngineScript()
    script.setSourceCode(src)
    script.setName(name)
    script.setWorldId(world)
    script.setInjectionPoint(injection_point)
    script.setRunsOnSubFrames(on_subframes)
    return script
