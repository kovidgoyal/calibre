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
Contains the logic for parsing feeds.
'''
import time, logging
from datetime import datetime

from libprs500.web.feeds.feedparser import parse

class Article(object):
    
    time_offset = datetime.now() - datetime.utcnow()

    def __init__(self, id, title, url, summary, published, content):
        self.downloaded = False
        self.id = id
        self.title = title
        self.url = url
        self.summary = summary
        self.content = content
        self.date = published
        self.utctime = datetime(*self.date[:6])
        self.localtime = self.utctime + self.time_offset
                
    def __repr__(self):
        return \
(u'''\
Title       : %s
URL         : %s
Summary     : %s
Date        : %s
Has content : %s
'''%(self.title, self.url, self.summary[:20]+'...', self.localtime.strftime('%a, %d %b, %Y %H:%M'),
     bool(self.content))).encode('utf-8')

    def __str__(self):
        return repr(self)


class Feed(object):

    def __init__(self):
        '''
        Parse a feed into articles.
        '''
        self.logger = logging.getLogger('feeds2disk')
        
    def populate_from_feed(self, feed, title=None, oldest_article=7, 
                           max_articles_per_feed=100):
        entries = feed.entries
        feed = feed.feed
        self.title        = feed.get('title', 'Unknown feed') if not title else title
        self.description  = feed.get('description', '')
        image             = feed.get('image', {})
        self.image_url    = image.get('href', None)
        self.image_width  = image.get('width', 88)
        self.image_height = image.get('height', 31)
        self.image_alt    = image.get('title', '')
        
        self.articles = []
        self.id_counter = 0
        self.added_articles = []
        
        self.oldest_article = oldest_article
        
        for item in entries:
            if len(self.articles) >= max_articles_per_feed:
                break
            self.parse_article(item)

    def parse_article(self, item):
        id = item.get('id', 'internal id#'+str(self.id_counter))
        if id in self.added_articles:
            return
        published = item.get('date_parsed', time.gmtime())
        self.id_counter += 1
        self.added_articles.append(id)
        
        title = item.get('title', 'Untitled article')
        link  = item.get('link',  None)
        description = item.get('summary', None)
        
        content = '\n'.join(i.value for i in item.get('content', []))
        if not content.strip():
            content = None
        
        article = Article(id, title, link, description, published, content)
        delta = datetime.utcnow() - article.utctime
        if delta.days*24*3600 + delta.seconds <= 24*3600*self.oldest_article:
            self.articles.append(article)
        else:
            self.logger.debug('Skipping article %s (%s) from feed %s as it is too old.'%(title, article.localtime.strftime('%a, %d %b, %Y %H:%M'), self.title))
        
    def __iter__(self):
        return iter(self.articles)
    
    def __len__(self):
        return len(self.articles)
    
    def __repr__(self):
        res = [('%20s\n'%'').replace(' ', '_')+repr(art) for art in self]
        
        return '\n'+'\n'.join(res)+'\n'
    
    def __str__(self):
        return repr(self)
    
    def __bool__(self):
        for article in self:
            if getattr(article, 'downloaded', False):
                return True
        return False


def feed_from_xml(raw_xml, title=None, oldest_article=7, max_articles_per_feed=100):
    feed = parse(raw_xml)
    pfeed = Feed()
    pfeed.populate_from_feed(feed, title=title, 
                            oldest_article=oldest_article,
                            max_articles_per_feed=max_articles_per_feed)
    return pfeed
