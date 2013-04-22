# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 3 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, 2013, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import base64
import mimetypes
import re
import urllib
from contextlib import closing

from lxml import etree

from calibre import browser, url_slash_cleaner
from calibre.constants import __version__
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult

class GutenbergStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://www.gutenberg.org/catalog/osd-books.xml'
    web_url = 'http://m.gutenberg.org/'

    def search(self, query, max_results=10, timeout=60):
        '''
        Gutenberg's ODPS feed is poorly implmented and has a number of issues
        which require very special handling to fix the results.

        Issues:
          * "Sort Alphabetically" and "Sort by Release Date" are returned
            as book entries.
          * The author is put into a "content" tag and not the author tag.
          * The link to the book itself goes to an odps page which we need
            to turn into a link to a web page.
          * acquisition links are not part of the search result so we have
            to go to the odps item itself. Detail item pages have a nasty
            note saying:
              DON'T USE THIS PAGE FOR SCRAPING. 
              Seriously. You'll only get your IP blocked.
            We're using the ODPS feed because people are getting blocked with
            the previous implementation so due to this using ODPS probably
            won't solve this issue.
          * Images are not links but base64 encoded strings. They are also not
            real cover images but a little blue book thumbnail.
        '''

        url = 'http://m.gutenberg.org/ebooks/search.opds/?query=' + urllib.quote_plus(query)

        counter = max_results
        br = browser(user_agent='calibre/'+__version__)
        with closing(br.open(url, timeout=timeout)) as f:
            doc = etree.fromstring(f.read())
            for data in doc.xpath('//*[local-name() = "entry"]'):
                if counter <= 0:
                    break

                counter -= 1

                s = SearchResult()

                # We could use the <link rel="alternate" type="text/html" ...> tag from the
                # detail odps page but this is easier.
                id = ''.join(data.xpath('./*[local-name() = "id"]/text()')).strip()
                s.detail_item = url_slash_cleaner('%s/ebooks/%s' % (self.web_url, re.sub('[^\d]', '', id)))
                if not s.detail_item:
                    continue

                s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
                s.author = ', '.join(data.xpath('./*[local-name() = "content"]//text()')).strip()
                if not s.title or not s.author:
                    continue

                # Get the formats and direct download links.
                with closing(br.open(id, timeout=timeout/4)) as nf:
                    ndoc = etree.fromstring(nf.read())
                    for link in ndoc.xpath('//*[local-name() = "link" and @rel = "http://opds-spec.org/acquisition"]'):
                        type = link.get('type')
                        href = link.get('href')
                        if type:
                            ext = mimetypes.guess_extension(type)
                            if ext:
                                ext = ext[1:].upper().strip()
                                s.downloads[ext] = href

                s.formats = ', '.join(s.downloads.keys())
                if not s.formats:
                    continue

                for link in data.xpath('./*[local-name() = "link"]'):
                    rel = link.get('rel')
                    href = link.get('href')
                    type = link.get('type')

                    if rel and href and type:
                        if rel in ('http://opds-spec.org/thumbnail', 'http://opds-spec.org/image/thumbnail'):
                            if href.startswith('data:image/png;base64,'):
                                s.cover_data = base64.b64decode(href.replace('data:image/png;base64,', ''))

                yield s
