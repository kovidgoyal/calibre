# -*- coding: utf-8 -*-


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
        self.create_browser = None

    def __eq__(self, other):
        return self.title == other.title and self.author == other.author and self.store_name == other.store_name and self.formats == other.formats

    def __hash__(self):
        return hash((self.title, self.author, self.store_name, self.formats))

    def __str__(self):
        items = []
        for x in 'store_name title author price formats detail_item cover_url'.split():
            items.append('\t%s=%r' % (x, getattr(self, x)))
        return 'SearchResult(\n%s\n)' % '\n'.join(items)
    __repr__ = __str__
    __unicode__ = __str__
