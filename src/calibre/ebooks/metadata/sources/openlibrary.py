#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2011, Kovid Goyal <kovid@kovidgoyal.net>

# annotations: the source plugins are downloaded and run by older calibre versions
# using older Python, so annotations must not be evaluated at runtime
from __future__ import absolute_import, annotations, division, print_function, unicode_literals

from typing import TYPE_CHECKING

from calibre.ebooks.metadata.sources.base import Source

if TYPE_CHECKING:
    from collections.abc import Sequence
    from threading import Event

    from calibre.ebooks.metadata.sources.base import CoverQueue, Identifiers
    from calibre.utils.logging import Log

try:
    from calibre.utils.localization import _
except ImportError:
    pass


class OpenLibrary(Source):
    name = 'Open Library'
    version = (1, 0, 3)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads covers from The Open Library')

    capabilities = frozenset(['cover'])

    OPENLIBRARY = 'https://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false'

    def download_cover(
        self,
        log: Log,
        result_queue: CoverQueue,
        abort: Event,
        title: str | None = None,
        authors: Sequence[str] | None = None,
        identifiers: Identifiers | None = None,
        timeout: float = 30,
        get_best_cover: bool = False,
    ) -> None:
        if identifiers is None:
            identifiers = {}
        if 'isbn' not in identifiers:
            return
        isbn = identifiers['isbn']
        br = self.browser
        try:
            ans = br.open_novisit(self.OPENLIBRARY % isbn, timeout=timeout).read()
            result_queue.put((self, ans))
        except Exception as e:
            getcode = getattr(e, 'getcode', None)
            if callable(getcode) and getcode() == 404:
                log.error('No cover for ISBN: %r found' % isbn)
            else:
                log.exception('Failed to download cover for ISBN:', isbn)
