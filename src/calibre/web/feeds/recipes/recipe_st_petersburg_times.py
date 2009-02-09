#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
sptimes.ru
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class PetersburgTimes(BasicNewsRecipe):
    title                 = u'The St. Petersburg Times'
    __author__            = 'Darko Miletic'
    description           = 'News from Russia'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    language = _('English')
    INDEX = 'http://www.sptimes.ru'
    
    def parse_index(self):
        articles = []
        soup = self.index_to_soup(self.INDEX)
        
        for item in soup.findAll('a', attrs={'class':'story_link_o'}):
            if item.has_key('href'):
                url    = self.INDEX + item['href'].replace('action_id=2','action_id=100')
                title  = self.tag_to_string(item)
                c_date = strftime('%A, %d %B, %Y')
                description = ''
                articles.append({
                                 'title':title,
                                 'date':c_date,
                                 'url':url,
                                 'description':description
                                })
        return [(soup.head.title.string, articles)]
