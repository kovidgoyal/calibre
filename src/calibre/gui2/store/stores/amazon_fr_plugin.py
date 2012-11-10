# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.store.stores.amazon_uk_plugin import AmazonUKKindleStore

class AmazonFRKindleStore(AmazonUKKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    aff_id = {'tag': 'charhale-21'}
    store_link = 'http://www.amazon.fr/livres-kindle/b?ie=UTF8&node=695398031&ref_=sa_menu_kbo1&_encoding=UTF8&tag=%(tag)s&linkCode=ur2&camp=1642&creative=19458' % aff_id
    store_link_details = 'http://www.amazon.fr/gp/redirect.html?ie=UTF8&location=http://www.amazon.fr/dp/%(asin)s&tag=%(tag)s&linkCode=ur2&camp=1634&creative=6738'
    search_url = 'http://www.amazon.fr/s/?url=search-alias%3Ddigital-text&field-keywords='

