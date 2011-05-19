# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

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

class ArchiveOrgStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.archive.org/details/texts'
        
        if detail_item:
            detail_item = url_slash_cleaner('http://www.archive.org' + detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        query = query + ' AND mediatype:texts'
        url = 'http://www.archive.org/search.php?query=' + urllib.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//td[@class="hitCell"]'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//a[@class="titleLink"]/@href'))
                if not id:
                    continue

                title = ''.join(data.xpath('.//a[@class="titleLink"]//text()'))
                authors = data.xpath('.//text()')
                if not authors:
                    continue
                author = None
                for a in authors:
                    if '-' in a:
                        author = a.replace('-', ' ').strip()
                        if author:
                            break
                if not author:
                    continue

                counter -= 1
                
                s = SearchResult()
                s.title = title.strip()
                s.author = author.strip()
                s.price = '$0.00'
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                
                yield s

    def get_details(self, search_result, timeout):
        url = url_slash_cleaner('http://www.archive.org' + search_result.detail_item)

        br = browser()
        with closing(br.open(url, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            formats = ', '.join(idata.xpath('//p[@id="dl" and @class="content"]//a/text()'))
            search_result.formats = formats.upper()
            
        return True
