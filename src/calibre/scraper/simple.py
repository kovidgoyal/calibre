#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
from functools import lru_cache
from qt.core import QApplication
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from calibre.constants import cache_dir


@lru_cache(maxsize=4)
def create_profile(cache_name='simple', allow_js=False):
    from calibre.utils.random_ua import random_common_chrome_user_agent
    ans = QWebEngineProfile(cache_name, QApplication.instance())
    ans.setHttpUserAgent(random_common_chrome_user_agent())
    ans.setHttpCacheMaximumSize(0)  # managed by webengine
    ans.setCachePath(os.path.join(cache_dir(), 'scraper', cache_name))
    s = ans.settings()
    a = s.setAttribute
    a(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
    a(QWebEngineSettings.WebAttribute.JavascriptEnabled, allow_js)
    s.setUnknownUrlSchemePolicy(QWebEngineSettings.UnknownUrlSchemePolicy.DisallowUnknownUrlSchemes)
    a(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    a(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
    # ensure javascript cannot read from local files
    a(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    a(QWebEngineSettings.WebAttribute.AllowWindowActivationFromJavaScript, False)
    return s


class SimpleScraper(QWebEnginePage):

    def __init__(self, source, parent=None):
        super().__init__(create_profile(source), parent=parent)
        self.setAudioMuted(True)

    def javaScriptAlert(self, url, msg):
        pass

    def javaScriptConfirm(self, url, msg):
        return True

    def javaScriptPrompt(self, url, msg, defval):
        return True, defval

    def javaScriptConsoleMessage(self, level, message, line_num, source_id):
        pass
