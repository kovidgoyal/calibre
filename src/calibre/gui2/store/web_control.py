# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
from urlparse import urlparse

from PyQt5.Qt import QNetworkCookieJar, QNetworkProxy
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

from calibre import USER_AGENT, get_proxies
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.gui2 import choose_save_file, NO_URL_FORMATTING
from calibre.gui2.ebook_download import show_download_info
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import ascii_filename
from calibre.web import get_download_filename


class NPWebView(QWebView):

    def __init__(self, *args):
        QWebView.__init__(self, *args)
        self.gui = None
        self.tags = ''
        self.create_browser = None

        self._page = NPWebPage()
        self.setPage(self._page)
        self.cookie_jar = QNetworkCookieJar()
        self.page().networkAccessManager().setCookieJar(self.cookie_jar)

        http_proxy = get_proxies().get('http', None)
        if http_proxy:
            proxy_parts = urlparse(http_proxy)
            proxy = QNetworkProxy()
            proxy.setType(QNetworkProxy.HttpProxy)
            if proxy_parts.username:
                proxy.setUser(proxy_parts.username)
            if proxy_parts.password:
                proxy.setPassword(proxy_parts.password)
            if proxy_parts.hostname:
                proxy.setHostName(proxy_parts.hostname)
            if proxy_parts.port:
                proxy.setPort(proxy_parts.port)
            self.page().networkAccessManager().setProxy(proxy)

        self.page().setForwardUnsupportedContent(True)
        self.page().unsupportedContent.connect(self.start_download)
        self.page().downloadRequested.connect(self.start_download)
        self.page().networkAccessManager().sslErrors.connect(self.ignore_ssl_errors)

    def createWindow(self, type):
        if type == QWebPage.WebBrowserWindow:
            return self
        else:
            return None

    def set_gui(self, gui):
        self.gui = gui

    def set_tags(self, tags):
        self.tags = tags

    def start_download(self, request):
        if not self.gui:
            return

        url = unicode(request.url().toString(NO_URL_FORMATTING))
        cf = self.get_cookies()

        filename = get_download_filename(url, cf)
        ext = os.path.splitext(filename)[1][1:].lower()
        filename = ascii_filename(filename[:60] + '.' + ext)
        if ext not in BOOK_EXTENSIONS:
            if ext == 'acsm':
                from calibre.gui2.dialogs.confirm_delete import confirm
                if not confirm('<p>' + _('This e-book is a DRMed EPUB file.  '
                          'You will be prompted to save this file to your '
                          'computer. Once it is saved, open it with '
                          '<a href="https://www.adobe.com/solutions/ebook/digital-editions.html">'
                          'Adobe Digital Editions</a> (ADE).<p>ADE, in turn '
                          'will download the actual e-book, which will be a '
                          '.epub file. You can add this book to calibre '
                          'using "Add Books" and selecting the file from '
                          'the ADE library folder.'),
                          'acsm_download', self):
                    return
            name = choose_save_file(self, 'web-store-download-unknown', _('File is not a supported e-book type. Save to disk?'), initial_filename=filename)
            if name:
                self.gui.download_ebook(url, cf, name, name, False, create_browser=self.create_browser)
        else:
            show_download_info(filename, self)
            self.gui.download_ebook(url, cf, filename, tags=self.tags, create_browser=self.create_browser)

    def ignore_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors(errors)

    def get_cookies(self):
        '''
        Writes QNetworkCookies to Mozilla cookie .txt file.

        :return: The file path to the cookie file.
        '''
        cf = PersistentTemporaryFile(suffix='.txt')

        cf.write('# Netscape HTTP Cookie File\n\n')

        for c in self.page().networkAccessManager().cookieJar().allCookies():
            cookie = []
            domain = unicode(c.domain())

            cookie.append(domain)
            cookie.append('TRUE' if domain.startswith('.') else 'FALSE')
            cookie.append(unicode(c.path()))
            cookie.append('TRUE' if c.isSecure() else 'FALSE')
            cookie.append(unicode(c.expirationDate().toTime_t()))
            cookie.append(unicode(c.name()))
            cookie.append(unicode(c.value()))

            cf.write('\t'.join(cookie))
            cf.write('\n')

        cf.close()
        return cf.name


class NPWebPage(QWebPage):

    def userAgentForUrl(self, url):
        return USER_AGENT
