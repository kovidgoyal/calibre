# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 1 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.store.stores.amazon_uk_plugin import AmazonUKKindleStore

class AmazonITKindleStore(AmazonUKKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    aff_id = {'tag': 'httpcharles07-21'}
    store_link = ('http://www.amazon.it/ebooks-kindle/b?_encoding=UTF8&'
                  'node=827182031&tag=%(tag)s&ie=UTF8&linkCode=ur2&camp=3370&creative=23322')
    store_link_details = ('http://www.amazon.it/gp/redirect.html?ie=UTF8&'
                          'location=http://www.amazon.it/dp/%(asin)s&tag=%(tag)s&'
                          'linkCode=ur2&camp=3370&creative=23322')
    search_url = 'http://www.amazon.it/s/?url=search-alias%3Ddigital-text&field-keywords='

    author_article = 'di '
