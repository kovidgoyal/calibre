# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import mimetypes
import urllib

from PyQt4.Qt import QUrl

from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from calibre.utils.opensearch import Client

class OpenSearchStore(StorePlugin):

    open_search_url = ''
    web_url = ''

    def open(self, parent=None, detail_item=None, external=False):
        if external or self.config.get('open_external', False):
            open_url(QUrl(detail_item if detail_item else self.url))
        else:
            d = WebStoreDialog(self.gui, self.url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        if not hasattr(self, 'open_search_url'):
            return

        client = Client(self.open_search_url)
        results = client.search(urllib.quote_plus(query), max_results)
        
        counter = max_results
        for r in results:
            if counter <= 0:
                break            
            counter -= 1
            
            s = SearchResult()
            
            s.detail_item = r.get('id', '')
            
            links = r.get('links', None)
            for l in links:
                if l.get('rel', None):
                    if l['rel'] == u'http://opds-spec.org/image/thumbnail':
                        s.cover_url = l.get('href', '')
                    elif l['rel'] == u'http://opds-spec.org/acquisition/buy':
                        s.detail_item = l.get('href', s.detail_item)
                    elif l['rel'] == u'http://opds-spec.org/acquisition':
                        s.downloads.append((l.get('type', ''), l.get('href', '')))

            formats = []
            for mime, url in s.downloads:
                ext = mimetypes.guess_extension(mime)
                if ext:
                    formats.append(ext[1:])
            s.formats = ', '.join(formats)

            s.title = r.get('title', '')
            s.author = r.get('author', '')
            s.price = r.get('price', '')
            
            yield s
