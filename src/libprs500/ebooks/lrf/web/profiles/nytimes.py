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
Profile to download the New York Times
'''
import re

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class NYTimes(DefaultProfile):
    
    title   = 'The New York Times'
    timefmt = ' [%a, %d %b, %Y]'
    needs_subscription = True
    max_recursions = 2
    
    preprocess_regexps = \
            [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
              [
               # Remove header bar
               (r'(<body.*?>).*?<h1', lambda match: match.group(1)+'<h1'),
               (r'<div class="articleTools">.*></ul>', lambda match : ''),
               # Remove footer bar
               (r'<\!--  end \#article -->.*', lambda match : '</body></html>'),
               (r'<div id="footer">.*', lambda match : '</body></html>'),
               ]
              ]
              
    def get_browser(self):
        br = DefaultProfile.get_browser()
        if self.username is not None and self.password is not None:
            br.open('http://www.nytimes.com/auth/login')
            br.select_form(name='login')
            br['USERID']   = self.username
            br['PASSWORD'] = self.password
            br.submit()
        return br
    
    def get_feeds(self):
        src = self.browser.open('http://www.nytimes.com/services/xml/rss/index.html').read()
        soup = BeautifulSoup(src[src.index('<html'):])
        feeds = []
        for link in soup.findAll('link', attrs={'type':'application/rss+xml'}):
            if link['title'] not in ['NYTimes.com Homepage', 'Obituaries', 'Pogue\'s Posts', 
                                     'Dining & Wine', 'Home & Garden', 'Multimedia',
                                     'Most E-mailed Articles', 
                                     'Automobiles', 'Fashion & Style', 'Television News',
                                     'Education']:
                feeds.append((link['title'], link['href']))            
        
        return feeds
    
    def print_version(self, url):
        return url + '?&pagewanted=print'
