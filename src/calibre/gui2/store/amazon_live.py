#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


from lxml import etree, html
from urllib.parse import urlencode

from calibre.scraper.simple import read_url
from calibre.gui2.store.search_result import SearchResult


module_version = 1  # needed for live updates


def search_amazon(self, query, max_results=10, timeout=60, write_html_to=None):
    field_keywords = self.FIELD_KEYWORDS
    uquery = self.SEARCH_BASE_QUERY.copy()
    uquery[field_keywords] = query

    def asbytes(x):
        if isinstance(x, type('')):
            x = x.encode('utf-8')
        return x
    uquery = {asbytes(k):asbytes(v) for k, v in uquery.items()}
    url = self.SEARCH_BASE_URL + '?' + urlencode(uquery)

    counter = max_results
    raw = read_url(self.scraper_storage, url, timeout=timeout)
    if write_html_to is not None:
        with open(write_html_to, 'w') as f:
            f.write(raw)
    doc = html.fromstring(raw)
    for result in doc.xpath('//div[contains(@class, "s-result-list")]//div[@data-index and @data-asin]'):
        kformat = ''.join(result.xpath('.//a[contains(text(), "{}")]//text()'.format(self.KINDLE_EDITION)))
        # Even though we are searching digital-text only Amazon will still
        # put in results for non Kindle books (author pages). So we need
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
        idx = aparts.index(self.BY)
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


def parse_details_amazon(self, idata, search_result):
    if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                    self.DRM_SEARCH_TEXT + '")])'):
        if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                        self.DRM_FREE_TEXT + '") and contains(b, "' +
                        self.DRM_SEARCH_TEXT + '")])'):
            search_result.drm = SearchResult.DRM_UNLOCKED
        else:
            search_result.drm = SearchResult.DRM_UNKNOWN
    else:
        search_result.drm = SearchResult.DRM_LOCKED
    return True


def get_details_amazon(self, search_result, timeout):
    url = self.DETAILS_URL + search_result.detail_item
    raw = read_url(self.scraper_storage, url, timeout=timeout)
    idata = html.fromstring(raw)
    return parse_details_amazon(self, idata, search_result)


def get_store_link_amazon(self, detail_item):
    return (self.DETAILS_URL + detail_item) if detail_item else self.STORE_LINK
