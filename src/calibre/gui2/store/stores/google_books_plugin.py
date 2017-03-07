# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 4  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import urllib
from contextlib import closing

from lxml import html
from PyQt5.Qt import QUrl

import html5lib
from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def parse_html(raw):
    return html5lib.parse(raw, namespaceHTMLElements=False, treebuilder='lxml')


def search_google(query, max_results=10, timeout=60, write_html_to=None):
    url = 'https://www.google.com/search?tbm=bks&q=' + urllib.quote_plus(query)

    br = browser()

    counter = max_results
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        doc = parse_html(raw)
        if write_html_to is not None:
            praw = html.tostring(doc, encoding='utf-8')
            open(write_html_to, 'wb').write(praw)
        for data in doc.xpath('//div[@id="rso"]//div[@class="g"]'):
            if counter <= 0:
                break

            id = ''.join(data.xpath('.//h3/a/@href'))
            if not id:
                continue

            title = ''.join(data.xpath('.//h3/a//text()'))
            authors = data.xpath('descendant::div[@class="s"]//a[@class="fl" and @href]//text()')
            while authors and authors[-1].strip().lower() in ('preview', 'read', 'more editions'):
                authors = authors[:-1]
            if not authors:
                continue
            author = ' & '.join(authors)

            counter -= 1

            s = SearchResult()
            s.title = title.strip()
            s.author = author.strip()
            s.detail_item = id.strip()
            s.drm = SearchResult.DRM_UNKNOWN

            yield s


class GoogleBooksStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'https://books.google.com/books'
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        for result in search_google(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        br = browser()
        with closing(br.open(search_result.detail_item, timeout=timeout)) as nf:
            doc = parse_html(nf.read())

            search_result.cover_url = ''.join(doc.xpath('//div[@class="sidebarcover"]//img/@src'))

            # Try to get the set price.
            price = ''.join(doc.xpath('//div[@id="gb-get-book-container"]//a/text()'))
            if 'read' in price.lower():
                price = 'Unknown'
            elif 'free' in price.lower() or not price.strip():
                price = '$0.00'
            elif '-' in price:
                a, b, price = price.partition(' - ')
            search_result.price = price.strip()

            search_result.formats = ', '.join(doc.xpath('//div[contains(@class, "download-panel-div")]//a/text()')).upper()
            if not search_result.formats:
                search_result.formats = _('Unknown')

        return True


if __name__ == '__main__':
    import sys
    for result in search_google(' '.join(sys.argv[1:]), write_html_to='/t/google.html'):
        print (result)
