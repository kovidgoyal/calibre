# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QUrl

from calibre.gui2 import open_url
from calibre.gui2.store.amazon_plugin import AmazonKindleStore

class AmazonDEKindleStore(AmazonKindleStore):
    '''
    For comments on the implementation, please see amazon_plugin.py
    '''

    search_url = 'http://www.amazon.de/s/url=search-alias%3Ddigital-text&field-keywords='
    details_url = 'http://amazon.de/dp/'
    drm_search_text = u'Gleichzeitige Verwendung von Geräten'
    drm_free_text = u'Keine Einschränkung'

    def open(self, parent=None, detail_item=None, external=False):
        aff_id = {'tag': 'charhale0a-21'}
        store_link = ('http://www.amazon.de/gp/redirect.html?ie=UTF8&site-redirect=de'
                     '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=19454'
                     '&location=http://www.amazon.de/ebooks-kindle/b?node=530886031') % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = ('http://www.amazon.de/gp/redirect.html?ie=UTF8'
                          '&location=http://www.amazon.de/dp/%(asin)s&site-redirect=de'
                          '&tag=%(tag)s&linkCode=ur2&camp=1638&creative=6742') % aff_id
        open_url(QUrl(store_link))
