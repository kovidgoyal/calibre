# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import mimetypes
import urllib
from contextlib import closing

from lxml import etree

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
#from calibre.utils.opensearch import Client
from calibre.utils.opensearch.description import Description
from calibre.utils.opensearch.query import Query

class OpenSearchStore(StorePlugin):

    open_search_url = ''
    web_url = ''

    def open(self, parent=None, detail_item=None, external=False):
        if not hasattr(self, 'web_url'):
            return
        
        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else self.web_url))
        else:
            d = WebStoreDialog(self.gui, self.web_url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        if not hasattr(self, 'open_search_url'):
            return

        description = Description(self.open_search_url)
        url_template = description.get_best_template()
        if not url_template:
            return
        oquery = Query(url_template)

        # set up initial values
        oquery.searchTerms = urllib.quote_plus(query)
        oquery.count = max_results
        url = oquery.url()
        
        counter = max_results
        br = browser()
        with closing(br.open(url, timeout=timeout)) as f:
            doc = etree.fromstring(f.read())
            for data in doc.xpath('//*[local-name() = "entry"]'):
                if counter <= 0:
                    break
            
                counter -= 1
    
                s = SearchResult()
                
                s.detail_item = ''.join(data.xpath('./*[local-name() = "id"]/text()'))

                for link in data.xpath('./*[local-name() = "link"]'):
                    rel = link.get('rel')
                    href = link.get('href')
                    type = link.get('type')
                    
                    if rel and href and type:
                        if rel in ('http://opds-spec.org/thumbnail', 'http://opds-spec.org/image/thumbnail'):
                            s.cover_url = href
                        elif rel == u'http://opds-spec.org/acquisition/buy':
                            s.detail_item = href
                        elif rel == u'http://opds-spec.org/acquisition':
                            if type:
                                ext = mimetypes.guess_extension(type)
                                if ext:
                                    ext = ext[1:].upper()
                                    s.downloads[ext] = href
                s.formats = ', '.join(s.downloads.keys())
                
                s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()'))
                s.author = ', '.join(data.xpath('./*[local-name() = "author"]//*[local-name() = "name"]//text()'))
                s.price = ' '.join(data.xpath('.//*[local-name() = "price"]//text()'))

                yield s
