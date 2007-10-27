##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
Profile to download Newsweek
'''
from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class Newsweek(DefaultProfile):
    
    title = 'Newsweek'
    max_recursions = 2
    timefmt  = ' [%d %b %Y]'
    html_description = True
    oldest_article        = 15
    
        
    def print_version(self, url):
        if not url.endswith('/'):
            url += '/'
        return url + 'output/print'
    
    def get_feeds(self):
        return [
             ('Top News', 'http://feeds.newsweek.com/newsweek/TopNews',),
             ('Periscope', 'http://feeds.newsweek.com/newsweek/periscope'),
             ('Politics', 'http://feeds.newsweek.com/headlines/politics'),
             ('Health', 'http://feeds.newsweek.com/headlines/health'),
             ('Business', 'http://feeds.newsweek.com/headlines/business'),
             ('Science and Technology', 'http://feeds.newsweek.com/headlines/technology/science'),
             ('National News', 'http://feeds.newsweek.com/newsweek/NationalNews'),
             ('World News', 'http://feeds.newsweek.com/newsweek/WorldNews'),
             ('Iraq', 'http://feeds.newsweek.com/newsweek/iraq'),
             ('Society', 'http://feeds.newsweek.com/newsweek/society'),
             ('Entertainment', 'http://feeds.newsweek.com/newsweek/entertainment'),
             ]
        
        