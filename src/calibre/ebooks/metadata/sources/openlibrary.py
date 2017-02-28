#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.metadata.sources.base import Source


class OpenLibrary(Source):

    name = 'Open Library'
    version = (1, 0, 0)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads covers from The Open Library')

    capabilities = frozenset(['cover'])

    OPENLIBRARY = 'https://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false'

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        if 'isbn' not in identifiers:
            return
        isbn = identifiers['isbn']
        br = self.browser
        try:
            ans = br.open_novisit(self.OPENLIBRARY%isbn, timeout=timeout).read()
            result_queue.put((self, ans))
        except Exception as e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
                log.error('No cover for ISBN: %r found'%isbn)
            else:
                log.exception('Failed to download cover for ISBN:', isbn)
