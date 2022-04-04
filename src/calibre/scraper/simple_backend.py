#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import secrets
import sys
import time
from functools import lru_cache
from qt.core import QApplication, QEventLoop, QUrl
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from calibre.constants import cache_dir
from calibre.utils.webengine import create_script, insert_scripts


def canonicalize_qurl(qurl):
    qurl = qurl.adjusted(
        QUrl.UrlFormattingOption.StripTrailingSlash | QUrl.UrlFormattingOption.NormalizePathSegments | QUrl.UrlFormattingOption.RemoveFragment
    )
    if qurl.path() == '/':
        qurl = qurl.adjusted(QUrl.UrlFormattingOption.RemovePath)
    return qurl


@lru_cache(maxsize=None)
def create_profile(cache_name='', allow_js=False):
    from calibre.utils.random_ua import random_common_chrome_user_agent
    if cache_name:
        ans = QWebEngineProfile(cache_name, QApplication.instance())
        ans.setCachePath(os.path.join(cache_dir(), 'scraper', cache_name))
    else:
        ans = QWebEngineProfile(QApplication.instance())
    ans.setHttpUserAgent(random_common_chrome_user_agent())
    ans.setHttpCacheMaximumSize(0)  # managed by webengine
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
    js = P('scraper.js', allow_user_override=False, data=True).decode('utf-8')
    ans.token = secrets.token_hex()
    js = js.replace('TOKEN', ans.token)
    insert_scripts(ans, create_script('scraper.js', js))
    return ans


class SimpleScraper(QWebEnginePage):

    def __init__(self, source='', parent=None):
        profile = create_profile(source)
        self.token = profile.token
        self.is_being_tested = source == 'test'
        super().__init__(profile, parent)
        self.setAudioMuted(True)
        self.loadStarted.connect(self.load_started)
        self.loadFinished.connect(self.load_finished)
        self.loadProgress.connect(self.load_progress)

    def print(self, *a):
        print(*a, file=sys.stderr)

    def load_started(self):
        if self.is_being_tested:
            self.print(f'load_started: {self.is_current_url=} {self.requestedUrl()=}')
        if self.is_current_url:
            self.current_fetch['load_started'] = True

    def load_finished(self, ok):
        if self.is_being_tested:
            self.print(f'load_finished: {ok=} {self.is_current_url=}')
        if self.is_current_url:
            self.current_fetch['load_finished'] = True
            self.current_fetch['load_was_ok'] = ok
            if not ok and self.is_current_url:
                self.current_fetch['working'] = False

    def load_progress(self, progress):
        if self.is_being_tested:
            self.print(f'load_progress: {progress=} {self.is_current_url=}')
        if self.is_current_url:
            self.current_fetch['end_time'] = time.monotonic() + self.current_fetch['timeout']

    def javaScriptAlert(self, url, msg):
        pass

    def javaScriptConfirm(self, url, msg):
        return True

    def javaScriptPrompt(self, url, msg, defval):
        return True, defval

    @property
    def is_current_url(self):
        if not hasattr(self, 'current_fetch'):
            return False
        return canonicalize_qurl(self.requestedUrl()) == self.current_fetch['fetching_url']

    def javaScriptConsoleMessage(self, level, message, line_num, source_id):
        parts = message.split(maxsplit=1)
        if len(parts) == 2 and parts[0] == self.token:
            msg = json.loads(parts[1])
            t = msg.get('type')
            if t == 'print':
                print(msg['text'], file=sys.stderr)
            elif t == 'domready':
                if self.is_being_tested:
                    self.print(f'domready: {self.is_current_url=}')
                if self.is_current_url:
                    self.triggerAction(QWebEnginePage.WebAction.Stop)
                    self.current_fetch['working'] = False
                    if not msg.get('failed'):
                        self.current_fetch['html'] = msg['html']

    def fetch(self, url_or_qurl, timeout=60):
        fetching_url = QUrl(url_or_qurl)
        self.current_fetch = {
            'timeout': timeout, 'end_time': time.monotonic() + timeout,
            'fetching_url': canonicalize_qurl(fetching_url), 'working': True,
            'load_started': False
        }
        self.load(fetching_url)
        try:
            app = QApplication.instance()
            while self.current_fetch['working'] and time.monotonic() < self.current_fetch['end_time']:
                app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            ans = self.current_fetch.get('html')
            if ans is None:
                eurl = fetching_url.toString()
                if self.current_fetch['working']:
                    raise TimeoutError(f'Timed out loading HTML from: {eurl}')
                raise ValueError(f'Failed to load HTML from: {eurl}')
            return ans
        finally:
            del self.current_fetch
