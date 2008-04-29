#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Daily Dilbert
'''
import os
from calibre.web.feeds.news import CustomIndexRecipe
from calibre.ptempfile import PersistentTemporaryDirectory

class Dilbert(CustomIndexRecipe):
    
    title = 'Dilbert'
    __author__ = 'Kovid Goyal'
    description = 'Daily dilbert comic (from the last five days)'
    timefmt = ' [%d %b %Y]'
    
    feeds = [('Dilbert', 'http://feeds.feedburner.com/tapestrydilbert')]
    
    def get_article_url(self, item):
        return item.get('enclosures')[0].get('url')
    
    def custom_index(self):
        tdir = PersistentTemporaryDirectory('feeds2disk_dilbert')
        index = os.path.join(tdir, 'index.html')
        feed = self.parse_feeds()[0]
        
        res = ''
        for item in feed:
            res += '<h3>%s</h3><img style="page-break-after:always" src="%s" />\n'%(item.title, item.url)
        res = '<html><body><h1>Dilbert</h1>%s</body></html'%res
        open(index, 'wb').write(res)
        return index

