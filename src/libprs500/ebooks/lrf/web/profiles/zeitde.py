##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    Costomized to Die Zeit by S. Dorscht stdoonline@googlemail.com
##    Version 0.08
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
Fetch Die Zeit.
'''

from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class ZeitNachrichten(DefaultProfile):
    
    title = 'Die Zeit Nachrichten'
    timefmt = ' [%d %b %Y]'
    max_recursions = 2
    max_articles_per_feed = 40
    html_description = True
    no_stylesheets = True

    
    def get_feeds(self): 
        return [ ('Zeit.de', 'http://newsfeed.zeit.de/news/index') ] 
    
    def print_version(self,url):
        return url.replace('http://www.zeit.de/', 'http://images.zeit.de/text/').replace('?from=rss', '')

