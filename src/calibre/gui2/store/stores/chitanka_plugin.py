# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Alex Stanev <alex@stanev.org>'
__docformat__ = 'restructuredtext en'

import re
import urllib
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

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
            d.exec_()

    def search(self, query, max_results=10, timeout=60):

        base_url = 'http://chitanka.info'
        url = base_url + '/search?q=' +  urllib.quote(query)
        counter = max_results

        # search for book title
        br = browser()
        with closing(br.open(url, timeout=timeout)) as f:
            f = unicode(f.read(), 'utf-8')
            doc = html.fromstring(f)

            for data in doc.xpath('//ul[@class="superlist booklist"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="booklink"]/@href'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//a[@class="booklink"]/img/@src'))
                title = ''.join(data.xpath('.//a[@class="booklink"]/i/text()'))
                author = ''.join(data.xpath('.//span[@class="bookauthor"]/a/text()'))
                fb2 = ''.join(data.xpath('.//a[@class="dl dl-fb2"]/@href'))
                epub = ''.join(data.xpath('.//a[@class="dl dl-epub"]/@href'))
                txt = ''.join(data.xpath('.//a[@class="dl dl-txt"]/@href'))

                # remove .zip extensions
                if fb2.find('.zip') != -1:
                    fb2 = fb2[:fb2.find('.zip')]
                if epub.find('.zip') != -1:
                    epub = epub[:epub.find('.zip')]
                if txt.find('.zip') != -1:
                    txt = txt[:txt.find('.zip')]

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.downloads['FB2'] = base_url + fb2.strip()
                s.downloads['EPUB'] = base_url + epub.strip()
                s.downloads['TXT'] = base_url + txt.strip()
                s.formats = 'FB2, EPUB, TXT, SFB'
                yield s

        # search for author names
        for data in doc.xpath('//ul[@class="superlist"][1]/li'):
            author_url = ''.join(data.xpath('.//a[contains(@href,"/person/")]/@href'))
            if counter <= 0:
                break

            br2 = browser()
            with closing(br2.open(base_url + author_url, timeout=timeout)) as f:
                if counter <= 0:
                    break
                f = unicode(f.read(), 'utf-8')
                doc2 = html.fromstring(f)

                # search for book title
                for data in doc2.xpath('//ul[@class="superlist booklist"]/li'):
                    if counter <= 0:
                        break

                    id = ''.join(data.xpath('.//a[@class="booklink"]/@href'))
                    if not id:
                        continue

                    cover_url = ''.join(data.xpath('.//a[@class="booklink"]/img/@src'))
                    title = ''.join(data.xpath('.//a[@class="booklink"]/i/text()'))
                    author = ''.join(data.xpath('.//span[@class="bookauthor"]/a/text()'))
                    fb2 = ''.join(data.xpath('.//a[@class="dl dl-fb2"]/@href'))
                    epub = ''.join(data.xpath('.//a[@class="dl dl-epub"]/@href'))
                    txt = ''.join(data.xpath('.//a[@class="dl dl-txt"]/@href'))

                    # remove .zip extensions
                    if fb2.find('.zip') != -1:
                        fb2 = fb2[:fb2.find('.zip')]
                    if epub.find('.zip') != -1:
                        epub = epub[:epub.find('.zip')]
                    if txt.find('.zip') != -1:
                        txt = txt[:txt.find('.zip')]

                    counter -= 1

                    s = SearchResult()
                    s.cover_url = cover_url
                    s.title = title.strip()
                    s.author = author.strip()
                    s.detail_item = id.strip()
                    s.drm = SearchResult.DRM_UNLOCKED
                    s.downloads['FB2'] = base_url + fb2.strip()
                    s.downloads['EPUB'] = base_url + epub.strip()
                    s.downloads['TXT'] = base_url + txt.strip()
                    s.formats = 'FB2, EPUB, TXT, SFB'
                    yield s
