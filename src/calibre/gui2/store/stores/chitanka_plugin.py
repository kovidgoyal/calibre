# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Alex Stanev <alex@stanev.org>'
__docformat__ = 'restructuredtext en'

from contextlib import closing
try:
    from urllib.parse import quote
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import quote, HTTPError

from lxml import html

from qt.core import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog


def parse_book_page(doc, base_url, counter):

    for data in doc.xpath('//div[@class="booklist"]/div/div'):
        if counter <= 0:
            break

        id = ''.join(data.xpath('.//div[@class="media-body"]/a[@class="booklink"]/@href')).strip()
        if not id:
            continue

        counter -= 1

        s = SearchResult()
        s.cover_url = 'http:' + ''.join(
            data.xpath('.//div[@class="media-left"]/a[@class="booklink"]/div/img/@src')).strip()

        s.title = ''.join(data.xpath('.//div[@class="media-body"]/a[@class="booklink"]/i/text()')).strip()
        alternative_headline = data.xpath('.//div[@class="media-body"]/div[@itemprop="alternativeHeadline"]/text()')
        if len(alternative_headline) > 0:
            s.title = "{} ({})".format(s.title, ''.join(alternative_headline).strip())

        s.author = ', '.join(data.xpath('.//div[@class="media-body"]/div[@class="bookauthor"]/span/a/text()')).strip(', ')
        s.detail_item = id
        s.drm = SearchResult.DRM_UNLOCKED
        s.downloads['FB2'] = base_url + ''.join(data.xpath(
            './/div[@class="media-body"]/div[@class="download-links"]/div/a[contains(@class,"dl-fb2")]/@href')).strip().replace(
            '.zip', '')
        s.downloads['EPUB'] = base_url + ''.join(data.xpath(
            './/div[@class="media-body"]/div[@class="download-links"]/div/a[contains(@class,"dl-epub")]/@href')).strip().replace(
            '.zip', '')
        s.downloads['TXT'] = base_url + ''.join(data.xpath(
            './/div[@class="media-body"]/div[@class="download-links"]/div/a[contains(@class,"dl-txt")]/@href')).strip().replace(
            '.zip', '')
        s.formats = 'FB2, EPUB, TXT'
        yield s

    return counter


class ChitankaStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://chitanka.info'

        if external or self.config.get('open_external', False):
            if detail_item:
                url = url + detail_item
            open_url(QUrl(url_slash_cleaner(url)))
        else:
            detail_url = None
            if detail_item:
                detail_url = url + detail_item
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec()

    def search(self, query, max_results=10, timeout=60):
        if isinstance(query, bytes):
            query = query.decode('utf-8')

        if len(query) < 3:
            return

        base_url = 'http://chitanka.info'
        url = base_url + '/search?q=' +  quote(query)
        counter = max_results

        # search for book title
        br = browser()
        try:
            with closing(br.open(url, timeout=timeout)) as f:
                f = f.read().decode('utf-8')
                doc = html.fromstring(f)
                counter = yield from parse_book_page(doc, base_url, counter)
                if counter <= 0:
                    return

                # search for author names
                for data in doc.xpath('//ul[@class="superlist"][1]/li/dl/dt'):
                    author_url = ''.join(data.xpath('.//a[contains(@href,"/person/")]/@href'))
                    if author_url == '':
                        continue

                    br2 = browser()
                    with closing(br2.open(base_url + author_url, timeout=timeout)) as f:
                        f = f.read().decode('utf-8')
                        doc = html.fromstring(f)
                        counter = yield from parse_book_page(doc, base_url, counter)
                        if counter <= 0:
                            break

        except HTTPError as e:
            if e.code == 404:
                return
            else:
                raise
