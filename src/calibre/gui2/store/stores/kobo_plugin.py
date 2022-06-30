# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 11  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import etree, html

from calibre import url_slash_cleaner
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def read_url(url, timeout=60):
    # Kobo uses Akamai which has some bot detection that uses network/tls
    # protocol data. So use the Chromium network stack to make the request
    from calibre.scraper.simple import read_url as ru
    return ru(read_url.storage, url, timeout=timeout)


read_url.storage = []


def search_kobo(query, max_results=10, timeout=60, write_html_to=None):
    from css_selectors import Select
    url = 'https://www.kobobooks.com/search/search.html?q=' + quote_plus(query)
    raw = read_url(url, timeout=timeout)
    if write_html_to is not None:
        with open(write_html_to, 'w') as f:
            f.write(raw)
    doc = html.fromstring(raw)
    select = Select(doc)
    for i, item in enumerate(select('.result-items .item-wrapper.book')):
        if i == max_results:
            break
        for img in select('.item-image img[src]', item):
            cover_url = img.get('src')
            if cover_url.startswith('//'):
                cover_url = 'https:' + cover_url
            break
        else:
            cover_url = None

        for p in select('h2.title', item):
            title = etree.tostring(p, method='text', encoding='unicode').strip()
            for a in select('a[href]', p):
                url = a.get('href')
                break
            else:
                url = None
            break
        else:
            title = None
        if title:
            for p in select('p.subtitle', item):
                title += ' - ' + etree.tostring(p, method='text', encoding='unicode').strip()

        authors = []
        for a in select('.contributors a.contributor-name', item):
            authors.append(etree.tostring(a, method='text', encoding='unicode').strip())
        authors = authors_to_string(authors)

        for p in select('p.price', item):
            price = etree.tostring(p, method='text', encoding='unicode').strip()
            break
        else:
            price = None

        if title and authors and url:
            s = SearchResult()
            s.cover_url = cover_url
            s.title = title
            s.author = authors
            s.price = price
            s.detail_item = url
            s.formats = 'EPUB'
            s.drm = SearchResult.DRM_UNKNOWN

            yield s


class KoboStore(BasicStoreConfig, StorePlugin):

    minimum_calibre_version = (5, 40, 1)

    def open(self, parent=None, detail_item=None, external=False):
        if detail_item:
            purl = detail_item
            url = purl
        else:
            purl = None
            url = 'https://kobo.com'

        if external or self.config.get('open_external', False):
            open_url(url_slash_cleaner(url))
        else:
            d = WebStoreDialog(self.gui, url, parent, purl)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        for result in search_kobo(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        raw = read_url(search_result.detail_item, timeout=timeout)
        idata = html.fromstring(raw)
        if idata.xpath('boolean(//div[@class="bookitem-secondary-metadata"]//li[contains(text(), "Download options")])'):
            if idata.xpath('boolean(//div[@class="bookitem-secondary-metadata"]//li[contains(text(), "DRM-Free")])'):
                search_result.drm = SearchResult.DRM_UNLOCKED
            if idata.xpath('boolean(//div[@class="bookitem-secondary-metadata"]//li[contains(text(), "Adobe DRM")])'):
                search_result.drm = SearchResult.DRM_LOCKED
        else:
            search_result.drm = SearchResult.DRM_UNKNOWN
        return True


if __name__ == '__main__':
    import sys

    for result in search_kobo(' '.join(sys.argv[1:]), write_html_to='/t/kobo.html'):
        print(result)
