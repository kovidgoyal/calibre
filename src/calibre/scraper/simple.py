#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import json
import os
import secrets
import sys
import time
from functools import lru_cache
from qt.core import QApplication, QEventLoop, QUrl, pyqtSignal
from qt.webengine import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from calibre.constants import cache_dir
from calibre.gui2.webengine import create_script, insert_scripts


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
    js = P('scraper.js', allow_user_override=False, data=True).decode('utf-8')
    ans.token = secrets.token_hex()
    js = js.replace('TOKEN', ans.token)
    insert_scripts(ans, create_script('scraper.js', js))
    return ans


class SimpleScraper(QWebEnginePage):

    html_fetched = pyqtSignal(str)

    def __init__(self, source, parent=None):
        profile = create_profile(source)
        self.token = profile.token
        super().__init__(profile, parent)
        self.setAudioMuted(True)
        self.fetching_url = QUrl('invalid://XXX')
        self.last_fetched_html = ''

    def javaScriptAlert(self, url, msg):
        pass

    def javaScriptConfirm(self, url, msg):
        return True

    def javaScriptPrompt(self, url, msg, defval):
        return True, defval

    def javaScriptConsoleMessage(self, level, message, line_num, source_id):
        parts = message.split(maxsplit=1)
        if len(parts) == 2 and parts[0] == self.token:
            msg = json.loads(parts[1])
            t = msg.get('type')
            if t == 'print':
                print(msg['text'], file=sys.stderr)
            elif t == 'domready':
                if self.url() == self.fetching_url:
                    if msg.get('failed'):
                        self.last_fetched_html = '!'
                    else:
                        self.last_fetched_html = msg['html']
                    self.html_fetched.emit(self.last_fetched_html)

    def start_fetch(self, url_or_qurl):
        self.fetching_url = QUrl(url_or_qurl)
        self.load(self.fetching_url)

    def fetch(self, url_or_qurl, timeout=60):
        self.last_fetched_html = ''
        self.start_fetch(url_or_qurl)
        app = QApplication.instance()
        end = time.monotonic() + timeout
        while not self.last_fetched_html and time.monotonic() < end:
            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        ans = self.last_fetched_html
        self.last_fetched_html = ''
        if ans == '!':
            raise ValueError(f'Failed to load HTML from {url_or_qurl}')
        return ans


if __name__ == '__main__':
    app = QApplication([])
    s = SimpleScraper('test')
    s.fetch('file:///t/raw.html')
    del s
    del app
