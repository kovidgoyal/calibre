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
'''New York Times from RSS feeds.'''
import os, tempfile, shutil

from libprs500 import __appname__, iswindows, browser
from libprs500.ebooks.BeautifulSoup import BeautifulSoup
from libprs500.ebooks.lrf.web import build_index, parse_feeds

RSS = 'http://www.nytimes.com/services/xml/rss/index.html'
LOGIN = 'http://www.nytimes.com/auth/login'

def get_feeds(browser):
    src = browser.open(RSS).read()
    soup = BeautifulSoup(src[src.index('<html'):])
    feeds = []
    for link in soup.findAll('link', attrs={'type':'application/rss+xml'}):
        if link['title'] not in ['NYTimes.com Homepage', 'Obituaries', 'Pogue\'s Posts', 
                                 'Dining & Wine', 'Home & Garden', 'Multimedia',
                                 'Most E-mailed Articles', 
                                 'Automobiles', 'Fashion & Style', 'Television News',
                                 'Education']:
            feeds.append((link['title'], link['href']))
        #else: print link['title']
    
    return feeds

def initialize(profile):
    profile['temp dir'] = tempfile.mkdtemp(prefix=__appname__+'_')
    profile['browser'] = login(profile)
    feeds = get_feeds(profile['browser'])
    articles = parse_feeds(feeds, profile['browser'], lambda x: x + '?&pagewanted=print',
                           oldest_article=2)
    index = build_index('The New York Times', articles, profile['temp dir'])
    profile['url'] = 'file:'+ ('' if iswindows else '//') + index
    profile['timefmt'] = ' [%a, %d %b, %Y]'
    profile['max_recursions'] =  2                 
    profile['title']          = 'The New York Times'
    
    
def finalize(profile):
    if os.path.isdir(profile['temp dir']):
        shutil.rmtree(profile['temp dir'])
 

def login(profile):
    br = browser()
    if profile['username'] and profile['password']:
        br.open(LOGIN)
        br.select_form(name='login')
        br['USERID']   = profile['username']
        br['PASSWORD'] = profile['password']
        br.submit()
    return br
      

if __name__ == '__main__':
    feeds = get_feeds()
    articles = parse_feeds(feeds)
    print articles

