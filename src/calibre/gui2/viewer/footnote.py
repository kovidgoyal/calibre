#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json

from PyQt5.Qt import QUrl

class Footnotes(object):

    def __init__(self, document):
        self.document = document
        self.clear()

    def clear(self):
        self.footnote_data_cache = {}

    def get_footnote_data(self, url):
        current_url = unicode(self.document.mainFrame().baseUrl().toLocalFile())
        if not current_url:
            return  # Not viewing a local file
        fd = self.footnote_data_cache.get(current_url, None)
        if fd is None:
            raw = self.document.javascript('window.calibre_extract.get_footnote_data()', typ='string')
            try:
                fd = frozenset(QUrl(x).toLocalFile() for x in json.loads(raw))
            except Exception:
                fd = frozenset()
            self.footnote_data_cache[current_url] = fd


