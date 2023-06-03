# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 6  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import re
try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from calibre import url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import browser_get_url, StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def search(query, max_results=10, timeout=60, save_raw=None):
    url = 'https://www.smashwords.com/books/search?query=' + quote(query)

    br = browser()
    try:
        br.set_simple_cookie('adultOff', 'erotica', '.smashwords.com', path='/')
    except AttributeError:
        pass  # old version of mechanize

    doc = browser_get_url(url, timeout, browser=br, save_html_to=save_raw)
    counter = max_results
    for data in doc.xpath('//div[@id="pageContent"]//div[contains(@class, "library-book")]'):
        if counter <= 0:
            break
        data = html.fromstring(html.tostring(data))

        id_a = ''.join(data.xpath('//span[contains(@class, "library-title")]/a/@href'))
        if not id_a:
            continue

        cover_url = ''.join(data.xpath('//img[contains(@class, "book-list-image")]/@src'))

        title = ''.join(data.xpath('.//span[contains(@class, "library-title")]//text()'))
        author = ''.join(data.xpath('.//span[contains(@class, "library-by-line")]/a//text()'))

        price = ''.join(data.xpath('.//div[@class="subnote"]//text()'))
        if 'Price:' in price:
            try:
                price = price.partition('Price:')[2]
                price = re.sub(r'\s', ' ', price).strip()
                price = price.split(' ')[0].strip()
            except Exception:
                price = 'Unknown'
        if price == 'Free!':
            price = '$0.00'

        counter -= 1

        s = SearchResult()
        s.cover_url = cover_url
        s.title = title.strip()
        s.author = author.strip()
        s.price = price
        s.detail_item = id_a
        s.drm = SearchResult.DRM_UNLOCKED

        yield s


class SmashwordsStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://www.smashwords.com/'

        aff_id = '?ref=usernone'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = '?ref=kovidgoyal'

        detail_url = None
        if detail_item:
            detail_url = url + detail_item + aff_id
        url = url + aff_id

        if external or self.config.get('open_external', False):
            open_url(url_slash_cleaner(detail_url if detail_url else url))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        for a in search(query, max_results=max_results, timeout=timeout):
            yield a

    def get_details(self, search_result, timeout):
        url = 'https://www.smashwords.com/'
        idata = browser_get_url(url + search_result.detail_item, timeout)
        search_result.formats = ', '.join(list(set(idata.xpath('//p//abbr//text()'))))
        return True


if __name__ == '__main__':
    import sys
    for r in search(' '.join(sys.argv[1:]), save_raw='/t/raw.html'):
        print(r)
