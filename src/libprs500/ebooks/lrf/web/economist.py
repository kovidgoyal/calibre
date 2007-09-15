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


import tempfile, shutil, os
from libprs500.ebooks.lrf.web import build_index, parse_feeds

RSS = 'http://economist.com/rss/'
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

from libprs500 import __appname__, iswindows, browser
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

def print_version(url):
    return url.replace('displaystory', 'PrinterFriendly').replace('&fsrc=RSS', '')

def get_feeds(browser):
    src = browser.open(RSS).read()
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
        if title not in TITLES:
            continue
        a = link.find('a')
        feeds.append((title, a['href'].strip()))
        
    return feeds
            
def initialize(profile):
    profile['temp dir'] = tempfile.mkdtemp(prefix=__appname__+'_')
    profile['browser'] = browser()
    feeds = get_feeds(profile['browser'])
    articles = parse_feeds(feeds, profile['browser'], print_version, max_articles_per_feed=20)
    index = build_index('The Economist', articles, profile['temp dir'])
    profile['url'] = 'file:'+ ('' if iswindows else '//') + index
    profile['timefmt'] = ' [%d %b %Y]'
    profile['max_recursions'] =  3                
    profile['title']          = 'The Economist'
    profile.pop('browser') # Needed as for some reason using the same browser instance causes timeouts
        
def finalize(profile):
    return
    if os.path.isdir(profile['temp dir']):
        shutil.rmtree(profile['temp dir'])
    