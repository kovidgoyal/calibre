#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import threading, re, json

from calibre import browser

class xISBN(object):

    QUERY = 'http://xisbn.worldcat.org/webservices/xid/isbn/%s?method=getEditions&format=json&fl=form,year,lang,ed'

    def __init__(self):
        self.lock = threading.RLock()
        self._data = []
        self._map = {}

        self.isbn_pat = re.compile(r'[^0-9X]', re.IGNORECASE)

    def purify(self, isbn):
        return self.isbn_pat.sub('', isbn.upper())

    def fetch_data(self, isbn):
        url = self.QUERY%isbn
        data = browser().open_novisit(url).read()
        data = json.loads(data)
        if data.get('stat', None) != 'ok':
            return []
        data = data.get('list', [])
        ans = []
        for rec in data:
            forms = rec.get('form', [])
            # Only get books, not audio/video
            forms = [x for x in forms if x in ('BA', 'BC', 'BB', 'DA')]
            if forms:
                ans.append(rec)
        return ans

    def get_data(self, isbn):
        isbn = self.purify(isbn)
        with self.lock:
            if isbn not in self._map:
                try:
                    data = self.fetch_data(isbn)
                except:
                    import traceback
                    traceback.print_exc()
                    data = []
                id_ = len(self._data)
                self._data.append(data)
                for rec in data:
                    for i in rec.get('isbn', []):
                        self._map[i] = id_
                self._map[isbn] = id_
            return self._data[self._map[isbn]]

    def get_associated_isbns(self, isbn):
        data = self.get_data(isbn)
        ans = set([])
        for rec in data:
            for i in rec.get('isbn', []):
                ans.add(i)
        return ans



xisbn = xISBN()

if __name__ == '__main__':
    import sys
    isbn = sys.argv[-1]
    print xisbn.get_data(isbn)
    print
    print xisbn.get_associated_isbns(isbn)


