# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 2  # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from contextlib import closing

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonCAKindleStore(StorePlugin):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    search_url = 'http://www.amazon.ca/s/url=search-alias%3Ddigital-text&field-keywords='
    details_url = 'http://amazon.ca/dp/'
    drm_search_text = u'Simultaneous Device Usage'
    drm_free_text = u'Unlimited'

    def open(self, parent=None, detail_item=None, external=False):
        #aff_id = {'tag': ''}
        # Use Kovid's affiliate id 30% of the time.
        # if random.randint(1, 10) in (1, 2, 3):
        #    aff_id['tag'] = 'calibrebs-20'
        # store_link = 'http://www.amazon.ca/Kindle-eBooks/b/?ie=UTF&node=1286228011&ref_=%(tag)s&ref=%(tag)s&tag=%(tag)s&linkCode=ur2&camp=1789&creative=390957' % aff_id
        store_link = 'http://www.amazon.ca/ebooks-kindle/b/ref=sa_menu_kbo?ie=UTF8&node=2980423011'
        if detail_item:
            # aff_id['asin'] = detail_item
            # store_link = 'http://www.amazon.ca/dp/%(asin)s/?tag=%(tag)s' % aff_id
            store_link = 'http://www.amazon.ca/dp/' + detail_item + '/'
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        url = self.search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())

            if doc.xpath('//div[@id = "atfResults" and contains(@class, "grid")]'):
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                        './/ul[contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                cover_xpath = './/img[contains(@class, "productImage")]/@src'
                title_xpath = './/h3[@class="newaps"]/a//text()'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                price_xpath = (
                        './/ul[contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and contains(@class, "bld")]/text()')
            elif doc.xpath('//div[@id = "atfResults" and contains(@class, "ilresults")]'):
                data_xpath = '//li[(@class="ilo")]'
                format_xpath = (
                        './/ul[contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                cover_xpath = './div[@class = "ilf"]/a/img[contains(@class, "ilo")]/@src'
                title_xpath = './/h3[@class="newaps"]/a//text()'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                # Results can be in a grid (table) or a column
                price_xpath = (
                        './/ul[contains(@class, "rsltL") or contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and contains(@class, "bld")]/text()')
            elif doc.xpath('//div[@id = "atfResults" and contains(@class, "list")]'):
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                        './/ul[contains(@class, "rsltL")]'
                        '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                cover_xpath = './/img[contains(@class, "productImage")]/@src'
                title_xpath = './/h3[@class="newaps"]/a//text()'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                price_xpath = (
                        './/ul[contains(@class, "rsltL")]'
                        '//span[contains(@class, "lrg") and contains(@class, "bld")]/text()')
            else:
                return

            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format.lower():
                    continue

                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin = data.xpath(asin_xpath)
                if asin:
                    asin = asin[0]
                else:
                    continue

                cover_url = ''.join(data.xpath(cover_xpath))

                title = ''.join(data.xpath(title_xpath))
                author = ''.join(data.xpath(author_xpath))
                try:
                    author = author.split('by ', 1)[1].split(" (")[0]
                except:
                    pass

                price = ''.join(data.xpath(price_xpath))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        url = self.details_url

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           self.drm_search_text + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               self.drm_free_text + '") and contains(b, "' +
                               self.drm_search_text + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True
