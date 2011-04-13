#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from urllib import quote

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source, Option

BASE_URL = 'http://isbndb.com/api/books.xml?access_key=%s&page_number=1&results=subjects,authors,texts&'


class ISBNDB(Source):

    name = 'ISBNDB'
    description = _('Downloads metadata from isbndb.com')

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['title', 'authors',
        'identifier:isbn', 'comments', 'publisher'])
    supports_gzip_transfer_encoding = True
    # Shortcut, since we have no cached cover URLS
    cached_cover_url_is_reliable = False

    options = (
            Option('isbndb_key', 'string', None, _('IsbnDB key:'),
                _('To use isbndb.com you have to sign up for a free account'
                    'at isbndb.com and get an access key.')),
            )

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

    @property
    def isbndb_key(self):
        return self.prefs['isbndb_key']

    def is_configured(self):
        return self.isbndb_key is not None

    def create_query(self, log, title=None, authors=None, identifiers={}): # {{{
        base_url = BASE_URL%self.isbndb_key
        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q = 'index1=isbn&value1='+isbn
        elif title or authors:
            tokens = []
            title_tokens = list(self.get_title_tokens(title))
            tokens += title_tokens
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            tokens += author_tokens
            tokens = [quote(t) for t in tokens]
            q = '+'.join(tokens)
            q = 'index1=combined&value1='+q

        if not q:
            return None
        if isinstance(q, unicode):
            q = q.encode('utf-8')
        return base_url + q

