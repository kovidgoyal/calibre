# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import time
from contextlib import closing
from threading import Thread

from lxml import html

from PyQt5.Qt import (pyqtSignal, QObject)

from calibre import browser
from calibre.gui2.store.search_result import SearchResult


class CacheUpdateThread(Thread, QObject):

    total_changed = pyqtSignal(int)
    update_progress = pyqtSignal(int)
    update_details = pyqtSignal(type(u''))

    def __init__(self, config, seralize_books_function, timeout):
        Thread.__init__(self)
        QObject.__init__(self)

        self.daemon = True
        self.config = config
        self.seralize_books = seralize_books_function
        self.timeout = timeout
        self._run = True

    def abort(self):
        self._run = False

    def run(self):
        url = 'https://www.mobileread.com/forums/ebooks.php?do=getlist&type=html'

        self.update_details.emit(_('Checking last download date.'))
        last_download = self.config.get('last_download', None)
        # Don't update the book list if our cache is less than one week old.
        if last_download and (time.time() - last_download) < 604800:
            return

        self.update_details.emit(_('Downloading book list from MobileRead.'))
        # Download the book list HTML file from MobileRead.
        br = browser()
        raw_data = None
        try:
            with closing(br.open(url, timeout=self.timeout)) as f:
                raw_data = f.read()
        except:
            return

        if not raw_data or not self._run:
            return

        self.update_details.emit(_('Processing books.'))
        # Turn books listed in the HTML file into SearchResults's.
        books = []
        try:
            data = html.fromstring(raw_data)
            raw_books = data.xpath('//ul/li')
            self.total_changed.emit(len(raw_books))

            for i, book_data in enumerate(raw_books):
                self.update_details.emit(
                        _('%(num)s of %(tot)s books processed.') % dict(
                            num=i, tot=len(raw_books)))
                book = SearchResult()
                book.detail_item = ''.join(book_data.xpath('.//a/@href'))
                book.formats = ''.join(book_data.xpath('.//i/text()'))
                book.formats = book.formats.strip()

                text = ''.join(book_data.xpath('.//a/text()'))
                if ':' in text:
                    book.author, q, text = text.partition(':')
                book.author = book.author.strip()
                book.title = text.strip()
                books.append(book)

                if not self._run:
                    books = []
                    break
                else:
                    self.update_progress.emit(i)
        except:
            pass

        # Save the book list and it's create time.
        if books:
            self.config['book_list'] = self.seralize_books(books)
            self.config['last_download'] = time.time()
