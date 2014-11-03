#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import json
from collections import defaultdict

from PyQt5.Qt import QUrl

from calibre import prints

class Footnotes(object):

    def __init__(self, view):
        self.view = view
        self.clear()

    def clear(self):
        self.footnote_data_cache = {}
        self.known_footnote_targets = defaultdict(set)

    def spine_index(self, path):
        try:
            return self.view.manager.iterator.spine.index(path)
        except (AttributeError, ValueError):
            return -1

    def load_footnote_data(self, current_url):
        fd = self.footnote_data_cache[current_url] = {}
        try:
            raw = self.view.document.javascript('window.calibre_extract.get_footnote_data()', typ='string')
            for x in json.loads(raw):
                if x not in fd:
                    qu = QUrl(x)
                    path = qu.toLocalFile()
                    si = self.spine_index(path)
                    if si > -1:
                        target = qu.fragment(QUrl.FullyDecoded)
                        fd[qu.toString()] = (path, target)
                        self.known_footnote_targets[path].add(target)
        except Exception:
            prints('Failed to get footnote data, with error:')
            import traceback
            traceback.print_exc()
        return fd

    def get_footnote_data(self, qurl):
        current_url = unicode(self.view.document.mainFrame().baseUrl().toLocalFile())
        if not current_url:
            return  # Not viewing a local file
        fd = self.footnote_data_cache.get(current_url)
        if fd is None:
            fd = self.load_footnote_data(current_url)
        return fd.get(qurl.toString())
