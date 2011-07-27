# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, Roman Mukhin <ramses_ru at hotmail.com>'
__docformat__ = 'restructuredtext en'

import random
import re
import urllib2

from contextlib import closing
from lxml import etree, html
from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class OzonRUStore(BasicStoreConfig, StorePlugin):
    shop_url = 'http://www.ozon.ru'
    
    def open(self, parent=None, detail_item=None, external=False):
        
        aff_id = '?partner=romuk'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id = '?partner=kovidgoyal'
        
        url = self.shop_url + aff_id
        detail_url = None
        if detail_item:
            # http://www.ozon.ru/context/detail/id/3037277/
            detail_url = self.shop_url + '/context/detail/id/' + urllib2.quote(detail_item) + aff_id
        
        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()        
        

    def search(self, query, max_results=10, timeout=60):
        search_url = self.shop_url + '/webservice/webservice.asmx/SearchWebService?'\
                    'searchText=%s&searchContext=ebook' % urllib2.quote(query)
                    
        counter = max_results
        br = browser()
        with closing(br.open(search_url, timeout=timeout)) as f:
            raw = xml_to_unicode(f.read(), strip_encoding_pats=True, assume_utf8=True)[0]
            doc = etree.fromstring(raw)
            for data in doc.xpath('//*[local-name() = "SearchItems"]'):
                if counter <= 0:
                    break
                counter -= 1
                        
                xp_template = 'normalize-space(./*[local-name() = "{0}"]/text())'
                
                s = SearchResult()
                s.detail_item = data.xpath(xp_template.format('ID'))
                s.title = data.xpath(xp_template.format('Name'))
                s.author = data.xpath(xp_template.format('Author'))
                s.price = data.xpath(xp_template.format('Price'))
                s.cover_url = data.xpath(xp_template.format('Picture'))
                if re.match("^\d+?\.\d+?$", s.price):
                    s.price = u'{:.2F} руб.'.format(float(s.price))
                yield s

    def get_details(self, search_result, timeout=60):
        url = self.shop_url + '/context/detail/id/' + urllib2.quote(search_result.detail_item)
        br = browser()

        result = False
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            
            # example where we are going to find formats
            # <div class="box">
            # ...
            #     <b>Доступные&nbsp;форматы:</b>
            #     <div class="vertpadd">.epub, .fb2, .pdf, .pdf, .txt</div>
            # ...
            # </div>
            xpt = u'normalize-space(//div[@class="box"]//*[contains(normalize-space(text()), "Доступные форматы:")][1]/following-sibling::div[1]/text())'
            formats = doc.xpath(xpt)
            if formats:
                result = True
                search_result.drm = SearchResult.DRM_UNLOCKED
                search_result.formats = ', '.join(_parse_ebook_formats(formats))
                # unfortunately no direct links to download books (only buy link)
                # search_result.downloads['BF2'] = self.shop_url + '/order/digitalorder.aspx?id=' + + urllib2.quote(search_result.detail_item)
        return result
    
def _parse_ebook_formats(formatsStr):
    '''
    Creates a list with displayable names of the formats
    
    :param formatsStr: string with comma separated book formats 
           as it provided by ozon.ru
    :return: a list with displayable book formats
    '''
    
    formatsUnstruct = formatsStr.lower()
    formats = []
    if 'epub' in formatsUnstruct:
        formats.append('ePub')
    if 'pdf' in formatsUnstruct:
        formats.append('PDF')
    if 'fb2' in formatsUnstruct:
        formats.append('FB2')
    if 'rtf' in formatsUnstruct:
        formats.append('RTF')
    if 'txt' in formatsUnstruct:
        formats.append('TXT')
    if 'djvu' in formatsUnstruct:
        formats.append('DjVu')
    if 'doc' in formatsUnstruct:
        formats.append('DOC')
    return formats
