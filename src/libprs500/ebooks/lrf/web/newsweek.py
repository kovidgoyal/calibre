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
'''Logic to create a Newsweek HTML aggregator from RSS feeds'''

import tempfile, os, shutil

from libprs500.ebooks.lrf.web import build_index, parse_feeds
from libprs500 import __appname__, iswindows, browser

RSS_FEEDS = [
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


def print_version(url):
    if '?' in url:
        url = url[:url.index('?')]
    if not url.endswith('/'):
        url += '/'
    return url + 'output/print'

def initialize(profile):
    profile['temp dir'] = tempfile.mkdtemp(prefix=__appname__+'_')
    profile['browser'] = browser()
    articles = parse_feeds(RSS_FEEDS, profile['browser'], print_version, 
                           max_articles_per_feed=20, oldest_article=15, 
                           html_description=True)
    index = build_index('Newsweek', articles, profile['temp dir'])
    profile['url'] = 'file:'+ ('' if iswindows else '//') + index
    profile['timefmt'] = ' [%d %b %Y]'
    profile['max_recursions'] =  2
    profile['title']          = 'Newsweek'
    profile['url'] = 'file:'+ ('' if iswindows else '//') +index

def finalize(profile):
    if os.path.isdir(profile['temp dir']):
        shutil.rmtree(profile['temp dir'])
