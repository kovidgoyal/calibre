# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.stores.amazon_uk_plugin import AmazonUKKindleStore

class AmazonDEKindleStore(AmazonUKKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    aff_id = {'tag': 'charhale0a-21'}
    store_link = ('http://www.amazon.de/gp/redirect.html?ie=UTF8&site-redirect=de'
                 '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=19454'
                 '&location=http://www.amazon.de/ebooks-kindle/b?node=530886031')
    store_link_details = ('http://www.amazon.de/gp/redirect.html?ie=UTF8'
                          '&location=http://www.amazon.de/dp/%(asin)s&site-redirect=de'
                          '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=6742')
    search_url = 'http://www.amazon.de/s/?url=search-alias%3Ddigital-text&field-keywords='

    author_article = 'von '
