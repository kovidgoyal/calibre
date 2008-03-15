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
'''
economist.com
'''
from libprs500.web.feeds.news import BasicNewsRecipe
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class Economist(BasicNewsRecipe):
    
    title = 'The Economist'
    oldest_article = 7.0
    INDEX = 'http://www.economist.com/printedition'
    remove_tags = [dict(name=['script', 'noscript', 'title'])]
    remove_tags_before = dict(name=lambda tag: tag.name=='title' and tag.parent.name=='body')
    
    def parse_index(self):
        soup = BeautifulSoup(self.browser.open(self.INDEX).read(), 
                             convertEntities=BeautifulSoup.HTML_ENTITIES)
        index_started = False
        feeds = {}
        key = None
        for tag in soup.findAll(['h1', 'h2']):
            text = ''.join(tag.findAll(text=True))                
            if tag.name == 'h1':
                if 'Classified ads' in text:
                    break
                if 'The world this week' in text:
                    index_started = True
                if not index_started:
                    continue
                feeds[text] = []
                key = text
                continue
            if key is None:
                continue
            a = tag.find('a', href=True)
            if a is not None:
                article = dict(title=text, 
                    url='http://www.economist.com'+a['href'].replace('displaystory', 'PrinterFriendly'), 
                    description='', content='', date='')
                feeds[key].append(article)
        return feeds