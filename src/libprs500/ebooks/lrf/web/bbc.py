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

RSS = 'http://news.bbc.co.uk/1/hi/help/3223484.stm'

from libprs500 import __appname__, iswindows, browser
from libprs500.ebooks.BeautifulSoup import BeautifulSoup


def get_feeds(browser):
    src = browser.open(RSS).read()
    soup = BeautifulSoup(src[src.index('<html'):])
    feeds = []
    ul =  soup.find('ul', attrs={'class':'rss'})
    for link in ul.findAll('a'):
        feeds.append((link.string, link['href']))
    return feeds

def initialize(profile):
    profile['temp dir'] = tempfile.mkdtemp(prefix=__appname__+'_')
    profile['browser'] = browser()
    feeds = get_feeds(profile['browser'])
    articles = parse_feeds(feeds, profile['browser'], lambda x: x.replace('http://', 'http://newsvote.bbc.co.uk/mpapps/pagetools/print/'))
    index = build_index('The BBC', articles, profile['temp dir'])
    profile['url'] = 'file:'+ ('' if iswindows else '//') + index
    profile['timefmt'] = ' [%a, %d %b, %Y]'
    profile['max_recursions'] =  2                 
    profile['title']          = 'The BBC'
    profile['no_stylesheets'] = True
    
def finalize(profile):
    if os.path.isdir(profile['temp dir']):
        shutil.rmtree(profile['temp dir'])



    