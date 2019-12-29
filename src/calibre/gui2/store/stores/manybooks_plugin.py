# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import mimetypes
from contextlib import closing

from lxml import etree

from calibre import browser
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.opensearch_store import OpenSearchOPDSStore
from calibre.gui2.store.search_result import SearchResult
from calibre.utils.opensearch.description import Description
from calibre.utils.opensearch.query import Query


def search_manybooks(query, max_results=10, timeout=60, open_search_url='http://www.manybooks.net/opds/'):
    '''
    Manybooks uses a very strange opds feed. The opds
    main feed is structured like a stanza feed. The
    search result entries give very little information
    and requires you to go to a detail link. The detail
    link has the wrong type specified (text/html instead
    of application/atom+xml).
    '''

    description = Description(open_search_url)
    url_template = description.get_best_template()
    if not url_template:
        return
    oquery = Query(url_template)

    # set up initial values
    oquery.searchTerms = query
    oquery.count = max_results
    url = oquery.url()

    counter = max_results
    br = browser()
    with closing(br.open(url, timeout=timeout)) as f:
        raw_data = f.read()
        raw_data = raw_data.decode('utf-8', 'replace')
        doc = etree.fromstring(raw_data, parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
        for data in doc.xpath('//*[local-name() = "entry"]'):
            if counter <= 0:
                break

            counter -= 1

            s = SearchResult()

            detail_links = data.xpath('./*[local-name() = "link" and @type = "text/html"]')
            if not detail_links:
                continue
            detail_link = detail_links[0]
            detail_href = detail_link.get('href')
            if not detail_href:
                continue

            s.detail_item = 'http://manybooks.net/titles/' + detail_href.split('tid=')[-1] + '.html'
            # These can have HTML inside of them. We are going to get them again later
            # just in case.
            s.title = ''.join(data.xpath('./*[local-name() = "title"]//text()')).strip()
            s.author = ', '.join(data.xpath('./*[local-name() = "author"]//text()')).strip()

            # Follow the detail link to get the rest of the info.
            with closing(br.open(detail_href, timeout=timeout/4)) as df:
                ddoc = etree.fromstring(df.read(), parser=etree.XMLParser(recover=True, no_network=True, resolve_entities=False))
                ddata = ddoc.xpath('//*[local-name() = "entry"][1]')
                if ddata:
                    ddata = ddata[0]

                    # This is the real title and author info we want. We got
                    # it previously just in case it's not specified here for some reason.
                    s.title = ''.join(ddata.xpath('./*[local-name() = "title"]//text()')).strip()
                    s.author = ', '.join(ddata.xpath('./*[local-name() = "author"]//text()')).strip()
                    if s.author.startswith(','):
                        s.author = s.author[1:]
                    if s.author.endswith(','):
                        s.author = s.author[:-1]

                    s.cover_url = ''.join(ddata.xpath('./*[local-name() = "link" and @rel = "http://opds-spec.org/thumbnail"][1]/@href')).strip()

                    for link in ddata.xpath('./*[local-name() = "link" and @rel = "http://opds-spec.org/acquisition"]'):
                        type = link.get('type')
                        href = link.get('href')
                        if type:
                            ext = mimetypes.guess_extension(type)
                            if ext:
                                ext = ext[1:].upper().strip()
                                s.downloads[ext] = href

            s.price = '$0.00'
            s.drm = SearchResult.DRM_UNLOCKED
            s.formats = 'EPUB, PDB (eReader, PalmDoc, zTXT, Plucker, iSilo), FB2, ZIP, AZW, MOBI, PRC, LIT, PKG, PDF, TXT, RB, RTF, LRF, TCR, JAR'

            yield s


class ManyBooksStore(BasicStoreConfig, OpenSearchOPDSStore):

    open_search_url = 'http://www.manybooks.net/opds/'
    web_url = 'http://manybooks.net'

    def search(self, query, max_results=10, timeout=60):
        for r in search_manybooks(query, max_results=max_results, timeout=timeout, open_search_url=self.open_search_url):
            yield r


if __name__ == '__main__':
    import sys
    for result in search_manybooks(' '.join(sys.argv[1:])):
        print(result)
