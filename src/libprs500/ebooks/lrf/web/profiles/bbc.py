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
Fetch the BBC.
'''
import re

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class BBC(DefaultProfile):
    
    title = 'The BBC'
    max_recursions = 2
    timefmt  = ' [%a, %d %b, %Y]'
    no_stylesheets = True
    
    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
              [
               # Remove footer from individual stories
               (r'<div class=.footer.>.*?Published', 
                lambda match : '<p></p><div class="footer">Published'),
               # Add some style info in place of disabled stylesheet
               (r'<link.*?type=.text/css.*?>', lambda match :
                '''<style type="text/css">
                    .headline {font-size: x-large;}
                    .fact { padding-top: 10pt  }
                    </style>'''),
               ]
                  ]
    
        
    def print_version(self, url):
        return url.replace('http://', 'http://newsvote.bbc.co.uk/mpapps/pagetools/print/')
    
    def get_feeds(self):
        src = self.browser.open('http://news.bbc.co.uk/1/hi/help/3223484.stm').read()
        soup = BeautifulSoup(src[src.index('<html'):])
        feeds = []
        ul =  soup.find('ul', attrs={'class':'rss'})
        for link in ul.findAll('a'):
            feeds.append((link.string, link['href']))
        return feeds

