# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import difflib
import heapq
import time
from contextlib import closing
from threading import RLock

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.utils.config import DynamicConfig

class MobileReadStore(StorePlugin):
    
    def genesis(self):
        self.config = DynamicConfig('store_' + self.name)
        self.rlock = RLock()
    
    def open(self, parent=None, detail_item=None, external=False):
        url = 'http://www.mobileread.com/'
        open_url(QUrl(detail_item if detail_item else url))

    def search(self, query, max_results=10, timeout=60):
        books = self.get_book_list(timeout=timeout)

        query = query.lower()
        query_parts = query.split(' ')
        matches = []
        s = difflib.SequenceMatcher()
        for x in books:
            ratio = 0
            t_string = '%s %s' % (x.author.lower(), x.title.lower())
            query_matches = []
            for q in query_parts:
                if q in t_string:
                    query_matches.append(q)
            for q in query_matches:
                s.set_seq2(q)
                for p in t_string.split(' '):
                    s.set_seq1(p)
                    ratio += s.ratio()
            if ratio > 0:
                matches.append((ratio, x))
        
        # Move the best scorers to head of list.
        matches = heapq.nlargest(max_results, matches)
        for score, book in matches:
            book.price = '$0.00'
            yield book

    def update_book_list(self, timeout=10):
        with self.rlock:
            url = 'http://www.mobileread.com/forums/ebooks.php?do=getlist&type=html'
            
            last_download = self.config.get(self.name + '_last_download', None)
            # Don't update the book list if our cache is less than one week old.
            if last_download and (time.time() - last_download) < 604800:
                return
            
            # Download the book list HTML file from MobileRead.
            br = browser()
            raw_data = None
            with closing(br.open(url, timeout=timeout)) as f:
                raw_data = f.read()
            
            if not raw_data:
                return
            
            # Turn books listed in the HTML file into BookRef's.
            books = []
            try:
                data = html.fromstring(raw_data)
                for book_data in data.xpath('//ul/li'):
                    book = BookRef()
                    book.detail_item = ''.join(book_data.xpath('.//a/@href'))
                    book.format = ''.join(book_data.xpath('.//i/text()'))
                    book.format = book.format.strip()
        
                    text = ''.join(book_data.xpath('.//a/text()'))
                    if ':' in text:
                        book.author, q, text = text.partition(':')
                    book.author = book.author.strip()
                    book.title = text.strip()
                    books.append(book)
            except:
                pass
    
            # Save the book list and it's create time.
            if books:
                self.config[self.name + '_last_download'] = time.time()
                self.config[self.name + '_book_list'] = books

    def get_book_list(self, timeout=10):
        self.update_book_list(timeout=timeout)
        return self.config.get(self.name + '_book_list', [])


class BookRef(SearchResult):
    
    def __init__(self):
        SearchResult.__init__(self)
        
        self.format = ''
