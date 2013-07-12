# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 3 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re
from contextlib import closing
from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult



class AmazonUKKindleStore(StorePlugin):
    aff_id = {'tag': 'calcharles-21'}
    store_link = ('http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&'
                  'location=http://www.amazon.co.uk/Kindle-eBooks/b?'
                  'ie=UTF8&node=341689031&ref_=sa_menu_kbo2&tag=%(tag)s&'
                  'linkCode=ur2&camp=1634&creative=19450')
    store_link_details = ('http://www.amazon.co.uk/gp/redirect.html?ie=UTF8&'
                          'location=http://www.amazon.co.uk/dp/%(asin)s&tag=%(tag)s&'
                          'linkCode=ur2&camp=1634&creative=6738')
    search_url = 'http://www.amazon.co.uk/s/?url=search-alias%3Ddigital-text&field-keywords='

    author_article = 'by '

    and_word = ' and '

    # This code is copy/pasted from from here to the other amazon EU. Do not
    # modify it in any other amazon EU plugin. Be sure to paste it into all
    # other amazon EU plugins when modified.

    # ---- Copy from here to end

    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):

        store_link = self.store_link % self.aff_id
        if detail_item:
            self.aff_id['asin'] = detail_item
            store_link = self.store_link_details % self.aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        url = self.search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        #print(url)
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            allText = f.read()
            doc = html.fromstring(allText)#.decode('latin-1', 'replace'))

            if doc.xpath('//div[@id = "atfResults" and contains(@class, "grid")]'):
                #print('grid form')
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                        './/ul[contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                cover_xpath = './/img[@class="productImage"]/@src'
                title_xpath = './/h3[@class="newaps"]/a//text()'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                price_xpath = (
                        './/ul[contains(@class, "rsltGridList")]'
                        '//span[contains(@class, "lrg") and contains(@class, "bld")]/text()')
            elif doc.xpath('//div[@id = "atfResults" and contains(@class, "ilresults")]'):
                #print('ilo form')
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
                #print('list form')
                data_xpath = '//div[contains(@class, "prod")]'
                format_xpath = (
                        './/ul[contains(@class, "rsltL")]'
                        '//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()')
                asin_xpath = '@name'
                cover_xpath = './/img[@class="productImage"]/@src'
                title_xpath = './/h3[@class="newaps"]/a//text()'
                author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
                price_xpath = (
                        './/ul[contains(@class, "rsltL")]'
                        '//span[contains(@class, "lrg") and contains(@class, "bld")]/text()')
            else:
                # URK -- whats this?
                print('unknown result table form for Amazon EU search')
                #with open("c:/amazon_search_results.html", "w") as out:
                #    out.write(allText)
                return


            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (authors pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format_ = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format_.lower():
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

                authors = ''.join(data.xpath(author_xpath))
                authors = re.sub('^' + self.author_article, '', authors)
                authors = re.sub(self.and_word, ' & ', authors)
                mo = re.match(r'(.*)(\(\d.*)$', authors)
                if mo:
                    authors = mo.group(1).strip()

                price = ''.join(data.xpath(price_xpath))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = authors.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.drm = SearchResult.DRM_UNKNOWN
                s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        pass

