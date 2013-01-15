# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, Roman Mukhin <ramses_ru at hotmail.com>'
__docformat__ = 'restructuredtext en'

import random
import re
import urllib2

from contextlib import closing
from lxml import etree
from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner, prints
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class LitResStore(BasicStoreConfig, StorePlugin):
    shop_url = u'http://www.litres.ru'
    #http://robot.litres.ru/pages/biblio_book/?art=174405

    def open(self, parent=None, detail_item=None, external=False):

        aff_id = u'?' + _get_affiliate_id()

        url = self.shop_url + aff_id
        detail_url = None
        if detail_item:
            # http://www.litres.ru/pages/biblio_book/?art=157074
            detail_url = self.shop_url + u'/pages/biblio_book/' + aff_id +\
                u'&art=' + urllib2.quote(detail_item)

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()


    def search(self, query, max_results=10, timeout=60):
        search_url = u'http://robot.litres.ru/pages/catalit_browser/?checkpoint=2000-01-02&'\
        'search=%s&limit=0,%s'
        search_url = search_url % (urllib2.quote(query), max_results)

        counter = max_results
        br = browser()
        br.addheaders.append( ['Accept-Encoding','gzip'] )

        with closing(br.open(search_url, timeout=timeout)) as r:
            ungzipResponse(r,br)
            raw= xml_to_unicode(r.read(), strip_encoding_pats=True, assume_utf8=True)[0]

            parser = etree.XMLParser(recover=True, no_network=True)
            doc = etree.fromstring(raw, parser=parser)
            for data in doc.xpath('//*[local-name() = "fb2-book"]'):
                if counter <= 0:
                    break
                counter -= 1

                try:
                    sRes = self.create_search_result(data)
                except Exception as e:
                    prints('ERROR: cannot parse search result #%s: %s'%(max_results - counter + 1, e))
                    continue
                yield sRes

    def get_details(self, search_result, timeout=60):
        pass

    def create_search_result(self, data):
        xp_template = 'normalize-space(@{0})'

        sRes = SearchResult()
        sRes.drm = SearchResult.DRM_UNLOCKED
        sRes.detail_item = data.xpath(xp_template.format('hub_id'))
        sRes.title = data.xpath('string(.//title-info/book-title/text()|.//publish-info/book-name/text())')
        #aut = concat('.//title-info/author/first-name', ' ')
        authors = data.xpath('.//title-info/author/first-name/text()|'\
        './/title-info/author/middle-name/text()|'\
        './/title-info/author/last-name/text()')
        sRes.author = u' '.join(map(unicode, authors))
        sRes.price = data.xpath(xp_template.format('price'))
        # cover vs cover_preview
        sRes.cover_url = data.xpath(xp_template.format('cover_preview'))
        sRes.price = format_price_in_RUR(sRes.price)

        types = data.xpath('//fb2-book//files/file/@type')
        fmt_set = _parse_ebook_formats(' '.join(types))
        sRes.formats = ', '.join(fmt_set)
        return sRes

def format_price_in_RUR(price):
    '''
    Try to format price according ru locale: '12 212,34 руб.'
    @param price: price in format like 25.99
    @return: formatted price if possible otherwise original value
    @rtype: unicode
    '''
    if price and re.match("^\d*?\.\d*?$", price):
        try:
            price = u'{:,.2F} руб.'.format(float(price))
            price = price.replace(',', ' ').replace('.', ',', 1)
        except:
            pass
    return price

def ungzipResponse(r,b):
    headers = r.info()
    if headers['Content-Encoding']=='gzip':
        import gzip
        gz = gzip.GzipFile(fileobj=r, mode='rb')
        data = gz.read()
        gz.close()
        #headers["Content-type"] = "text/html; charset=utf-8"
        r.set_data( data )
        b.set_response(r)

def _get_affiliate_id():
    aff_id = u'3623565'
    # Use Kovid's affiliate id 30% of the time.
    if random.randint(1, 10) in (1, 2, 3):
        aff_id = u'4084465'
    return u'lfrom=' + aff_id

def _parse_ebook_formats(formatsStr):
    '''
    Creates a set with displayable names of the formats

    :param formatsStr: string with comma separated book formats
           as it provided by ozon.ru
    :return: a list with displayable book formats
    '''

    formatsUnstruct = formatsStr.lower()
    formats = set()
    if 'fb2' in formatsUnstruct:
        formats.add('FB2')
    if 'html' in formatsUnstruct:
        formats.add('HTML')
    if 'txt' in formatsUnstruct:
        formats.add('TXT')
    if 'rtf' in formatsUnstruct:
        formats.add('RTF')
    if 'pdf' in formatsUnstruct:
        formats.add('PDF')
    if 'prc' in formatsUnstruct:
        formats.add('PRC')
    if 'lit' in formatsUnstruct:
        formats.add('PRC')
    if 'epub' in formatsUnstruct:
        formats.add('ePub')
    if 'rb' in formatsUnstruct:
        formats.add('RB')
    if 'isilo3' in formatsUnstruct:
        formats.add('ISILO3')
    if 'lrf' in formatsUnstruct:
        formats.add('LRF')
    if 'jar' in formatsUnstruct:
        formats.add('JAR')
    return formats
