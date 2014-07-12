# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 9  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2014, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from base64 import b64encode

from lxml import html

from PyQt4.Qt import QUrl

from calibre import url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.utils.ipc.simple_worker import fork_job, WorkerError

js_browser = '''
from calibre.web.jsbrowser.browser import Browser, Timeout
import urllib

def get_results(url, timeout):
    browser = Browser(default_timeout=timeout)
    browser.visit(url)
    browser.wait_for_element('#nw_content_main')
    return browser.html
    '''

class WoblinkStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        aff_root = 'https://www.a4b-tracking.com/pl/stat-click-text-link/16/58/'
        url = 'http://woblink.com/publication'

        aff_url = aff_root + str(b64encode(url))
        detail_url = None

        if detail_item:
            detail_url = aff_root + str(b64encode('http://woblink.com' + detail_item))

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else aff_url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url if detail_url else aff_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://woblink.com/ebooki-kategorie?query=' + urllib.quote_plus(query.encode('utf-8'))
        if max_results > 10:
            if max_results > 20:
                url += '&limit=30'
            else:
                url += '&limit=20'

        counter = max_results

        try:
            results = fork_job(js_browser,'get_results', (url, timeout,), module_is_source_code=True)
        except WorkerError as e:
            raise Exception('Could not get results: %s'%e.orig_tb)
        doc = html.fromstring(strip_encoding_declarations(results['result']))
        for data in doc.xpath('//div[@class="nw_katalog_lista_ksiazka"]'):
            if counter <= 0:
                break

            id = ''.join(data.xpath('.//div[@class="nw_katalog_lista_ksiazka_okladka nw_okladka"]/a[1]/@href'))
            if not id:
                continue

            cover_url = ''.join(data.xpath('.//div[@class="nw_katalog_lista_ksiazka_okladka nw_okladka"]/a[1]/img/@src'))
            title = ''.join(data.xpath('.//h2[@class="nw_katalog_lista_ksiazka_detale_tytul"]/a[1]/text()'))
            author = ', '.join(data.xpath('.//p[@class="nw_katalog_lista_ksiazka_detale_autor"]/a/text()'))
            price = ''.join(data.xpath('.//div[@class="nw_opcjezakupu_cena"]/text()'))
            formats = ', '.join(data.xpath('.//p[@class="nw_katalog_lista_ksiazka_detale_format"]/span/text()'))

            s = SearchResult()
            s.cover_url = 'http://woblink.com' + cover_url
            s.title = title.strip()
            s.author = author.strip()
            s.price = price + ' zł'
            s.detail_item = id.strip()
            s.formats = formats

            if 'DRM' in formats:
                s.drm = SearchResult.DRM_LOCKED

                counter -= 1
                yield s
            else:
                s.drm = SearchResult.DRM_UNLOCKED

                counter -= 1
                yield s
