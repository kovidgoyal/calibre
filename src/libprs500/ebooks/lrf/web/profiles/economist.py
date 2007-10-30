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
Fetch The Economist.
'''
import re

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class Economist(DefaultProfile):
    
    title = 'The Economist'
    timefmt = ' [%d %b %Y]'
    max_recursions = 3
    
    TITLES = [
          'The world this week',
          'Letters',
          'Briefings',
          'Special reports',
          'Britain',
          'Europe',
          'United States',
          'The Americas',
          'Middle East and Africa',
          'Asia',
          'International',
          'Business',
          'Finance and economics',
          'Science and technology',
          'Books and arts',
          'Indicators'
          ]
    
    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
            [
             # Remove advert
             (r'<noscript.*?</noscript>', lambda match: ''),
             ]
            ]
    
    def __init__(self, logger, verbose=False, username=None, password=None):
        DefaultProfile.__init__(self, username, password)
        self.browser = None # Needed as otherwise there are timeouts while fetching actual articles
    
    def print_version(self, url):
        return url.replace('displaystory', 'PrinterFriendly').replace('&fsrc=RSS', '')
    
    def get_feeds(self):
        src = self.browser.open('http://economist.com/rss/').read()
        soup = BeautifulSoup(src)
        feeds = []
        for ul in soup.findAll('ul'):
            lis =  ul.findAll('li')
            try:
                title, link = lis[0], lis[1]
            except IndexError:
                continue
            title = title.string
            if title:
                title = title.strip()
            if title not in self.__class__.TITLES:
                continue
            a = link.find('a')
            feeds.append((title, a['href'].strip()))
            
        return feeds
