# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 6  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, 2013, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import base64
import mimetypes
import re
from contextlib import closing
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from lxml import etree

from calibre import browser, url_slash_cleaner
from calibre.constants import __appname__, __version__
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult

web_url = 'http://m.gutenberg.org/'


def fix_url(url):
    if url and url.startswith('//'):
        url = 'http:' + url
    return url


def search(query, max_results=10, timeout=60, write_raw_to=None):
    url = 'http://m.gutenberg.org/ebooks/search.opds/?query=' + quote_plus(query)

    counter = max_results
    br = browser(user_agent='calibre/'+__version__)
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        if write_raw_to is not None:
            with open(write_raw_to, 'wb') as f:
                f.write(raw)
        doc = etree.fromstring(raw, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
        for data in doc.xpath('//*[local-name() = "entry"]'):
            if counter <= 0:
                break

            counter -= 1

            s = SearchResult()

            # We could use the <link rel="alternate" type="text/html" ...> tag from the
            # detail odps page but this is easier.
            id = fix_url(''.join(data.xpath('./*[local-name() = "id"]/text()')).strip())
            s.detail_item = url_slash_cleaner('%s/ebooks/%s' % (web_url, re.sub(r'[^\d]', '', id)))
            s.title = ' '.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
            s.author = ', '.join(data.xpath('./*[local-name() = "content"]//text()')).strip()
            if not s.title or not s.author:
                continue

            # Get the formats and direct download links.
            with closing(br.open(id, timeout=timeout/4)) as nf:
                ndoc = etree.fromstring(nf.read(), parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
                for link in ndoc.xpath('//*[local-name() = "link" and @rel = "http://opds-spec.org/acquisition"]'):
                    type = link.get('type')
                    href = link.get('href')
                    if type:
                        ext = mimetypes.guess_extension(type)
                        if ext:
                            ext = ext[1:].upper().strip()
                            s.downloads[ext] = fix_url(href)

            s.formats = ', '.join(s.downloads.keys())
            if not s.formats:
                continue

            for link in data.xpath('./*[local-name() = "link"]'):
                rel = link.get('rel')
                href = link.get('href')
                type = link.get('type')

                if rel and href and type:
                    href = fix_url(href)
                    if rel in ('http://opds-spec.org/thumbnail', 'http://opds-spec.org/image/thumbnail'):
                        if href.startswith('data:image/png;base64,'):
                            cdata = href.replace('data:image/png;base64,', '')
                            if not isinstance(cdata, bytes):
                                cdata = cdata.encode('ascii')
                            s.cover_data = base64.b64decode(cdata)

            yield s


class GutenbergStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://www.gutenberg.org/catalog/osd-books.xml'
    web_url = web_url

    def create_browser(self):
        from calibre import browser
        user_agent = '%s/%s' % (__appname__, __version__)
        return browser(user_agent=user_agent)

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
        for result in search(query, max_results, timeout):
            yield result


if __name__ == '__main__':
    import sys
    for result in search(' '.join(sys.argv[1:]), write_raw_to='/t/gutenberg.html'):
        print(result)
