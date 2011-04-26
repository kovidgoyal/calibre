# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QUrl

from calibre.gui2 import open_url
from calibre.gui2.store.amazon_plugin import AmazonKindleStore

class AmazonUKKindleStore(AmazonKindleStore):

    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'calcharles-21'}
        store_link = 'http://www.amazon.co.uk/Kindle-eBooks/b/?ie=UTF&node=1286228011&ref_=%(tag)s&ref=%(tag)s&tag=%(tag)s&linkCode=ur2&camp=1789&creative=390957' % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.co.uk/dp/%(asin)s/?tag=%(tag)s' % aff_id
        open_url(QUrl(store_link))

    search_url = 'http://www.amazon.co.uk/s/url=search-alias%3Ddigital-text&field-keywords='
    details_url = 'http://amazon.co.uk/dp/'

