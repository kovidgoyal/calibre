#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.metadata.sources.base import Source

class ISBNDB(Source):

    name = 'ISBNDB'
    description = _('Downloads metadata from isbndb.com')

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['title', 'authors',
        'identifier:isbn', 'comments', 'publisher'])
    supports_gzip_transfer_encoding = True

    def __init__(self, *args, **kwargs):
        Source.__init__(self, *args, **kwargs)

        prefs = self.prefs
        prefs.defaults['key_migrated'] = False
        prefs.defaults['isbndb_key'] = None

        if not prefs['key_migrated']:
            prefs['key_migrated'] = True
            try:
                from calibre.customize.ui import config
                key = config['plugin_customization']['IsbnDB']
                prefs['isbndb_key'] = key
            except:
                pass

        self.isbndb_key = prefs['isbndb_key']

    def is_configured(self):
        return self.isbndb_key is not None


