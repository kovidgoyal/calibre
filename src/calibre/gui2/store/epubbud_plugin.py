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

class EpubBudStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://epubbud.com/'

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        '''
        OPDS based search.
        
        We really should get the catelog from http://pragprog.com/catalog.opds
        and look for the application/opensearchdescription+xml entry.
        Then get the opensearch description to get the search url and
        format. However, we are going to be lazy and hard code it.
        '''
        url = 'http://www.epubbud.com/search.php?format=atom&q=' + urllib.quote_plus(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            # Use html instead of etree as html allows us
            # to ignore the namespace easily.
            doc = html.fromstring(f.read())
            for data in doc.xpath('//entry'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//id/text()'))
                if not id:
                    continue

                cover_url = ''.join(data.xpath('.//link[@rel="http://opds-spec.org/thumbnail"]/@href'))
                
                title = u''.join(data.xpath('.//title/text()'))
                author = u''.join(data.xpath('.//author/name/text()'))

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = '$0.00'
                s.detail_item = id.strip()
                s.drm = SearchResult.DRM_UNLOCKED
                s.formats = 'EPUB'
                
                yield s
