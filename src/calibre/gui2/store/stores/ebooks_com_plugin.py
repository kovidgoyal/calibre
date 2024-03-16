# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 4  # Needed for dynamic plugin loading

import re
from contextlib import closing

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def absolutize(url):
    if url.startswith('/'):
        url = 'https://www.ebooks.com' + url
    return url


def search_ec(query, max_results=10, timeout=60, write_html_to=''):
    import json
    from urllib.parse import parse_qs, urlparse
    url = 'https://www.ebooks.com/SearchApp/SearchResults.net?term=' + quote_plus(query)
    br = browser()
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
    if write_html_to:
        with open(write_html_to, 'wb') as d:
            d.write(raw)
    api = re.search(r'data-endpoint="(/api/search/.+?)"', raw.decode('utf-8')).group(1)
    counter = max_results
    url = absolutize(api)
    cc = parse_qs(urlparse(url).query)['CountryCode'][0]
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
    if write_html_to:
        with open(write_html_to + '.json', 'wb') as d:
            d.write(raw)
    data = json.loads(raw)
    for book in data['books']:
        if counter <= 0:
            break
        counter -= 1
        s = SearchResult()
        s.cover_url = absolutize(book['image_url'])
        s.title = book['title']
        s.author = ' & '.join(x['name'] for x in book['authors'])
        s.price = book['price']
        s.detail_item = absolutize(book['book_url'])
        s.ebooks_com_api_url = 'https://www.ebooks.com/api/book/?bookId={}&countryCode={}'.format(book["id"], cc)
        s.drm = SearchResult.DRM_UNKNOWN
        yield s


def ec_details(search_result, timeout=30, write_data_to=''):
    import json
    br = browser()
    with closing(br.open(search_result.ebooks_com_api_url, timeout=timeout)) as f:
        raw = f.read()
    if write_data_to:
        with open(write_data_to, 'wb') as d:
            d.write(raw)
    data = json.loads(raw)
    if 'drm' in data and 'drm_free' in data['drm']:
        search_result.drm = SearchResult.DRM_UNLOCKED if data['drm']['drm_free'] else SearchResult.DRM_LOCKED
    fmts = []
    for x in data['information']['formats']:
        x = x.split()[0]
        fmts.append(x)
    if fmts:
        search_result.formats = ', '.join(fmts).upper()


class EbookscomStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        m_url = 'http://www.dpbolvw.net/'
        h_click = 'click-4913808-10364500'
        d_click = 'click-4913808-10281551'

        url = m_url + h_click
        detail_url = None
        if detail_item:
            detail_url = m_url + d_click + detail_item

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        yield from search_ec(query, max_results, timeout)

    def get_details(self, search_result, timeout):
        ec_details(search_result, timeout)
        return True


if __name__ == '__main__':
    import sys
    results = tuple(search_ec(' '.join(sys.argv[1:]), write_html_to='/t/ec.html'))
    for result in results:
        print(result)
    ec_details(results[0], write_data_to='/t/ecd.json')
    print('-'*80)
    print(results[0])
