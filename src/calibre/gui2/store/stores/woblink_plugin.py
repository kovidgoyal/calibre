# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 14  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011-2017, Tomasz Długosz <tomek3d@gmail.com>'
__docformat__ = 'restructuredtext en'

import urllib
from base64 import b64encode

from lxml import html
from mechanize import Request

from PyQt5.Qt import QUrl

from calibre import url_slash_cleaner, browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def search(query, max_results=10, timeout=60):
    url = 'http://woblink.com/publication/ajax?mode=none&query=' + urllib.quote_plus(query.encode('utf-8'))
    if max_results > 10:
        if max_results > 20:
            url += '&limit=30'
        else:
            url += '&limit=20'
    br = browser(user_agent='CalibreCrawler/1.0')
    br.set_handle_gzip(True)
    rq = Request(url, headers={
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referrer':'http://woblink.com/ebooki-kategorie',
        'Cache-Control':'max-age=0',
    }, data=urllib.urlencode({
        'nw_filtry_filtr_zakrescen_formularz[min]':'0',
        'nw_filtry_filtr_zakrescen_formularz[max]':'350',
    }))
    r = br.open(rq)
    raw = r.read()
    doc = html.fromstring('<html><body>' + raw.decode('utf-8') + '</body></html>')
    counter = max_results

    for data in doc.xpath('//div[@class="nw_katalog_lista_ksiazka ebook " or @class="nw_katalog_lista_ksiazka ebook promocja"]'):
        if counter <= 0:
            break

        id = ''.join(data.xpath('.//div[@class="nw_katalog_lista_ksiazka_okladka nw_okladka"]/a[1]/@href'))
        if not id:
            continue

        cover_url = ''.join(data.xpath('.//div[@class="nw_katalog_lista_ksiazka_okladka nw_okladka"]/a[1]/img/@src'))
        title = ''.join(data.xpath('.//h3[@class="nw_katalog_lista_ksiazka_detale_tytul"]/a[1]/text()'))
        author = ', '.join(data.xpath('.//p[@class="nw_katalog_lista_ksiazka_detale_autor"]/a/text()'))
        price = ''.join(data.xpath('.//div[@class="nw_opcjezakupu_cena"]/span[2]/text()'))
        formats = ', '.join(data.xpath('.//p[@class="nw_katalog_lista_ksiazka_detale_format"]/span/text()'))

        s = SearchResult()
        s.cover_url = cover_url
        s.title = title.strip()
        s.author = author.strip()
        s.price = price + ' zł'
        s.detail_item = id.strip()
        s.formats = formats

        counter -= 1
        s.drm = SearchResult.DRM_LOCKED if 'DRM' in formats else SearchResult.DRM_UNLOCKED
        yield s


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
        for s in search(query, max_results, timeout):
            yield s

if __name__ == '__main__':
    from pprint import pprint
    pprint(list(search('Franciszek')))
