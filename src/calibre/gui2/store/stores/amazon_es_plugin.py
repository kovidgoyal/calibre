# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.stores.amazon_uk_plugin import AmazonUKKindleStore

class AmazonESKindleStore(AmazonUKKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    aff_id = {'tag': 'charhale09-21'}
    store_link = ('http://www.amazon.es/ebooks-kindle/b?_encoding=UTF8&'
                  'node=827231031&tag=%(tag)s&ie=UTF8&linkCode=ur2&camp=3626&creative=24790')
    store_link_details = ('http://www.amazon.es/gp/redirect.html?ie=UTF8&'
                          'location=http://www.amazon.es/dp/%(asin)s&tag=%(tag)s'
                          '&linkCode=ur2&camp=3626&creative=24790')
    search_url = 'http://www.amazon.es/s/?url=search-alias%3Ddigital-text&field-keywords='