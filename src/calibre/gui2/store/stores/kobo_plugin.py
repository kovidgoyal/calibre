# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 7  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import html, etree

from calibre import browser, url_slash_cleaner
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def search_kobo(query, max_results=10, timeout=60, write_html_to=None):
    from css_selectors import Select
    url = 'https://www.kobobooks.com/search/search.html?q=' + quote_plus(query)

    br = browser()

    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        if write_html_to is not None:
            with open(write_html_to, 'wb') as f:
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

            for p in select('p.title', item):
                title = etree.tostring(p, method='text', encoding='unicode').strip()
                for a in select('a[href]', p):
                    url = a.get('href')
                    break
                else:
                    url = None
                break
            else:
                title = None

            authors = []
            for a in select('p.contributor-list a.contributor-name', item):
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

    minimum_calibre_version = (2, 21, 0)

    def open(self, parent=None, detail_item=None, external=False):
        pub_id = '0dsO3kDu/AU'
        murl = 'https://click.linksynergy.com/fs-bin/click?id=%s&subid=&offerid=280046.1&type=10&tmpid=9310&RD_PARM1=http%%3A%%2F%%2Fkobo.com' % pub_id

        if detail_item:
            purl = 'https://click.linksynergy.com/link?id=%s&offerid=280046&type=2&murl=%s' % (pub_id, quote_plus(detail_item))
            url = purl
        else:
            purl = None
            url = murl

        if external or self.config.get('open_external', False):
            open_url(url_slash_cleaner(url))
        else:
            d = WebStoreDialog(self.gui, murl, parent, purl)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        for result in search_kobo(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            search_result.author = ', '.join(idata.xpath('.//h2[contains(@class, "author")]//a/text()'))
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
