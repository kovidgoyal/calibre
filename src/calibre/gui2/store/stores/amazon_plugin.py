#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 19  # Needed for dynamic plugin loading

from contextlib import closing
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from lxml import html, etree

from PyQt5.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

SEARCH_BASE_URL = 'https://www.amazon.com/s/'
SEARCH_BASE_QUERY = {'i': 'digital-text'}
DETAILS_URL = 'https://amazon.com/dp/'
STORE_LINK =  'https://www.amazon.com/Kindle-eBooks'
DRM_SEARCH_TEXT = 'Simultaneous Device Usage'
DRM_FREE_TEXT = 'Unlimited'


def get_user_agent():
    return 'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko'


def search_amazon(query, max_results=10, timeout=60,
                  write_html_to=None,
                  base_url=SEARCH_BASE_URL,
                  base_query=SEARCH_BASE_QUERY,
                  field_keywords='k'
                  ):
    uquery = base_query.copy()
    uquery[field_keywords] = query

    def asbytes(x):
        if isinstance(x, type('')):
            x = x.encode('utf-8')
        return x
    uquery = {asbytes(k):asbytes(v) for k, v in uquery.items()}
    url = base_url + '?' + urlencode(uquery)
    br = browser(user_agent=get_user_agent())

    counter = max_results
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        if write_html_to is not None:
            with open(write_html_to, 'wb') as f:
                f.write(raw)
        doc = html.fromstring(raw)
        for result in doc.xpath('//div[contains(@class, "s-result-list")]//div[@data-index and @data-asin]'):
            kformat = ''.join(result.xpath('.//a[contains(text(), "Kindle Edition")]//text()'))
            # Even though we are searching digital-text only Amazon will still
            # put in results for non Kindle books (author pages). Se we need
            # to explicitly check if the item is a Kindle book and ignore it
            # if it isn't.
            if 'kindle' not in kformat.lower():
                continue
            asin = result.get('data-asin')
            if not asin:
                continue

            cover_url = ''.join(result.xpath('.//img/@src'))
            title = etree.tostring(result.xpath('.//h2')[0], method='text', encoding='unicode')
            adiv = result.xpath('.//div[contains(@class, "a-color-secondary")]')[0]
            aparts = etree.tostring(adiv, method='text', encoding='unicode').split()
            idx = aparts.index('by')
            author = ' '.join(aparts[idx+1:]).split('|')[0].strip()
            price = ''
            for span in result.xpath('.//span[contains(@class, "a-price")]/span[contains(@class, "a-offscreen")]'):
                q = ''.join(span.xpath('./text()'))
                if q:
                    price = q
                    break

            counter -= 1

            s = SearchResult()
            s.cover_url = cover_url.strip()
            s.title = title.strip()
            s.author = author.strip()
            s.detail_item = asin.strip()
            s.price = price.strip()
            s.formats = 'Kindle'

            yield s


class AmazonKindleStore(StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        store_link = (DETAILS_URL + detail_item) if detail_item else STORE_LINK
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        for result in search_amazon(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        url = DETAILS_URL

        br = browser(user_agent=get_user_agent())
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           DRM_SEARCH_TEXT + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               DRM_FREE_TEXT + '") and contains(b, "' +
                               DRM_SEARCH_TEXT + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True


if __name__ == '__main__':
    import sys
    for result in search_amazon(' '.join(sys.argv[1:]), write_html_to='/t/amazon.html'):
        print(result)
