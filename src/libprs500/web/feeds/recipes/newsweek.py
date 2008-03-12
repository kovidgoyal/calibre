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
import re
from libprs500.web.feeds.news import BasicNewsRecipe
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class Newsweek(BasicNewsRecipe):

    title      = 'Newsweek'
    __author__ = 'Kovid Goyal'
    
    feeds = [
             ('Top News', 'http://feeds.newsweek.com/newsweek/TopNews',),
             'http://feeds.newsweek.com/newsweek/columnists/StevenLevy',
             ('Politics', 'http://feeds.newsweek.com/headlines/politics'),
             ('Health', 'http://feeds.newsweek.com/headlines/health'),
             ('Business', 'http://feeds.newsweek.com/headlines/business'),
             ('Science and Technology', 'http://feeds.newsweek.com/headlines/technology/science'),
             ('National News', 'http://feeds.newsweek.com/newsweek/NationalNews'),
             ('World News', 'http://feeds.newsweek.com/newsweek/WorldNews'),
             'http://feeds.newsweek.com/newsweek/Columnists/ChristopherDickey',
             'http://feeds.newsweek.com/newsweek/Columnists/FareedZakaria', 
             ('Iraq', 'http://feeds.newsweek.com/newsweek/iraq'),
             ('Society', 'http://feeds.newsweek.com/newsweek/society'),
             ('Entertainment', 'http://feeds.newsweek.com/newsweek/entertainment'),
             'http://feeds.newsweek.com/newsweek/columnists/GeorgeFWill', 
             'http://feeds.newsweek.com/newsweek/columnists/AnnaQuindlen',
             ]
    # For testing
    feeds = feeds[:2]
    max_articles_per_feed = 1
    
    keep_only_tags = [dict(name='div', id='content')]

    remove_tags = [
        dict(name=['script',  'noscript']),
        dict(name='div',  attrs={'class':['ad', 'SocialLinks', 'SocialLinksDiv', 'channel', 'bot', 'nav', 'top', 'EmailArticleBlock']}),
        dict(name='div',  attrs={'class':re.compile('box')}),
        dict(id=['ToolBox', 'EmailMain', 'EmailArticle', ])
    ]
    
    recursions = 1
    match_regexps = [r'http://www.newsweek.com/id/\S+/page/\d+']
    
    def postprocess_html(self,  soup):
        divs = list(soup.findAll('div', 'pagination'))
        divs[0].extract()
        if len(divs) > 1:
            soup.find('body')['style'] = 'page-break-after:avoid'
            divs[1].extract()            
            
            h1 = soup.find('h1')
            if h1:
                h1.extract()
            ai = soup.find('div', 'articleInfo')
            ai.extract()
        else:
            soup.find('body')['style'] = 'page-break-before:always; page-break-after:avoid;'
        return soup
    
    def get_current_issue(self):
        from urllib2 import urlopen # For some reason mechanize fails
        home = urlopen('http://www.newsweek.com').read() 
        soup = BeautifulSoup(home)
        img  = soup.find('img', alt='Current Magazine')
        if img and img.parent.has_key('href'):
            return urlopen(img.parent['href']).read()
        
    def get_cover_url(self):
        ci = self.get_current_issue()
        if ci is not None:
            soup = BeautifulSoup(ci)
            img = soup.find(alt='Cover')
            if img is not None and img.has_key('src'):
                small = img['src']
                return small.replace('coversmall', 'coverlarge')