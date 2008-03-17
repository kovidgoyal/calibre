#!/usr/bin/env  python

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Daily Dilbert
'''
import os
from libprs500.web.feeds.news import CustomIndexRecipe
from libprs500.ptempfile import PersistentTemporaryDirectory

class Dilbert(CustomIndexRecipe):
    
    title = 'Dilbert'
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

