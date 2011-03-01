# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

class SearchResult(object):
    
    def __init__(self):
        self.store_name = ''
        self.cover_url = ''
        self.cover_data = None
        self.title = ''
        self.author = ''
        self.price = ''
        self.detail_item = ''
