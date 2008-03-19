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
import re, string, time
from libprs500.web.feeds.news import BasicNewsRecipe
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class Newsweek(BasicNewsRecipe):

    title          = 'Newsweek'
    __author__     = 'Kovid Goyal'
    no_stylesheets = True
    
    extra_css = '#content { font:serif 12pt; }\n.story {font:12pt}\n.HorizontalHeader {font:18pt}\n.deck {font:16pt}'
    keep_only_tags = [dict(name='div', id='content')]

    remove_tags = [
        dict(name=['script',  'noscript']),
        dict(name='div',  attrs={'class':['ad', 'SocialLinks', 'SocialLinksDiv', 'channel', 'bot', 'nav', 'top', 'EmailArticleBlock']}),
        dict(name='div',  attrs={'class':re.compile('box')}),
        dict(id=['ToolBox', 'EmailMain', 'EmailArticle', ])
    ]
    
    recursions = 1
    match_regexps = [r'http://www.newsweek.com/id/\S+/page/\d+']
    
    
    def parse_index(self):
        soup = self.index_to_soup(self.get_current_issue())
        img = soup.find(alt='Cover')
        if img is not None and img.has_key('src'):
            small = img['src']
            self.cover_url = small.replace('coversmall', 'coverlarge')
            
        articles = {}
        key = None
        for tag in soup.findAll(['h5', 'h6']):
            if tag.name == 'h6':
                if key and not articles[key]:
                    articles.pop(key)
                key = self.tag_to_string(tag)
                if not key or not key.strip():
                    key = 'uncategorized'
                key = string.capwords(key)
                articles[key] = []
            elif tag.name == 'h5' and key is not None:
                a = tag.find('a', href=True)
                if a is not None:
                    title = self.tag_to_string(a)
                    if not title:
                        a = 'Untitled article'
                    art = {
                           'title' : title,
                           'url'   : a['href'],
                           'description':'', 'content':'',
                           'date': time.strftime('%a, %d %b', time.localtime())
                           }
                    if art['title'] and art['url']:
                        articles[key].append(art)
        return articles
        
    
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
    