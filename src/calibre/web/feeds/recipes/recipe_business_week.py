#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
businessweek.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class BusinessWeek(BasicNewsRecipe):
    title          = 'Business Week'
    description    = 'Business News, Stock Market and Financial Advice'
    __author__     = 'ChuckEggDotCom'
    oldest_article = 7
    max_articles_per_feed = 10

    remove_tags_before = dict(name='h1')
    remove_tags_after  = dict(id='footer')
    remove_tags = [dict(attrs={'class':['articleTools', 'post-tools', 'side_tool']}), 
                   dict(id=['footer', 'navigation', 'archive', 'side_search', 'blog_sidebar', 'side_tool', 'side_index']), 
                   dict(name='h2', attrs={'class':'listspace'}),
                   ]
    
    feeds          = [
                      (u'Top Stories', u'http://www.businessweek.com/topStories/rss/topStories.rss'), 
                      (u'Top News', u'http://www.businessweek.com/rss/bwdaily.rss'), 
                      (u'Asia', u'http://www.businessweek.com/rss/asia.rss'), 
                      (u'Autos', u'http://www.businessweek.com/rss/autos/index.rss'), 
                      (u'Classic Cars', u'http://www.businessweek.com/rss/autos/classic_cars/index.rss'),
                      (u'Hybrids', u'http://www.businessweek.com/rss/hybrids/index.rss'),  
                      (u'Europe', u'http://www.businessweek.com/rss/europe.rss'), 
                      (u'Auto Reviews', u'http://www.businessweek.com/rss/autos/reviews/index.rss'), 
                      (u'Innovation & Design', u'http://www.businessweek.com/rss/innovate.rss'), 
                      (u'Architecture', u'http://www.businessweek.com/rss/architecture.rss'), 
                      (u'Brand Equity', u'http://www.businessweek.com/rss/brandequity.rss'), 
                      (u'Auto Design', u'http://www.businessweek.com/rss/carbuff.rss'), 
                      (u'Game Room', u'http://www.businessweek.com/rss/gameroom.rss'), 
                      (u'Technology', u'http://www.businessweek.com/rss/technology.rss'), 
                      (u'Investing', u'http://www.businessweek.m/rss/investor.rss'), 
                      (u'Small Business', u'http://www.businessweek.com/rss/smallbiz.rss'), 
                      (u'Careers', u'http://www.businessweek.com/rss/careers.rss'), 
                      (u'B-Schools', u'http://www.businessweek.com/rss/bschools.rss'), 
                      (u'Magazine Selections', u'http://www.businessweek.com/rss/magazine.rss'), 
                      (u'CEO Guide to Tech', u'http://www.businessweek.com/rss/ceo_guide_tech.rss'),
                      ]

    def get_article_url(self, article):
        url = article.get('guid', None)
        if 'podcasts' in url:
            url = None
        return url
    
    def print_version(self, url):
        return url.replace('http://www.businessweek.com/', 'http://www.businessweek.com/print/')
