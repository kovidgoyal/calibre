# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

class SearchResult(object):

    DRM_LOCKED = 1
    DRM_UNLOCKED = 2
    DRM_UNKNOWN = 3

    def __init__(self):
        self.store_name = ''
        self.cover_url = ''
        self.cover_data = None
        self.title = ''
        self.author = ''
        self.price = ''
        self.detail_item = ''
        self.drm = None
        self.formats = ''
        # key = format in upper case.
        # value = url to download the file.
        self.downloads = {}
        self.affiliate = False
        self.plugin_author = ''

    def __eq__(self, other):
        return self.title == other.title and self.author == other.author and self.store_name == other.store_name and self.formats == other.formats
