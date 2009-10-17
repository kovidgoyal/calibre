#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
http://www.news.com.au/dailytelegraph/
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class DailyTelegraph(BasicNewsRecipe):
    title          = u'Daily Telegraph'
    __author__     = u'AprilHare'
    language = 'en'

    description    = u'News from down under'
    oldest_article = 2
    max_articles_per_feed = 10
    remove_tags_before = dict(name='div', attrs={'class':'article-title'})
    remove_tags = [dict(attrs={'class':['article-source', 'article-tools']})]
    remove_tags_after = dict(attrs={'class':re.compile('share-article')})
    
    feeds          = [
                      (u'Top Stories', u'http://feeds.news.com.au/public/rss/2.0/dtele_top_stories_253.xml'), 
                      (u'National News', u'http://feeds.news.com.au/public/rss/2.0/dtele_national_news_202.xml'), 
                      (u'World News', u'http://feeds.news.com.au/public/rss/2.0/dtele_world_news_204.xml'), 
                      (u'NSW and ACT', u'http://feeds.news.com.au/public/rss/2.0/dtele_nswact_225.xml'), 
                      (u'Arts', u'http://feeds.news.com.au/public/rss/2.0/dtele_art_444.xml'), 
                      (u'Business News', u'http://feeds.news.com.au/public/rss/2.0/dtele_business_226.xml'), 
                      (u'Entertainment News', u'http://feeds.news.com.au/public/rss/2.0/dtele_entertainment_news_201.xml'), 
                      (u'Lifestyle News', u'http://feeds.news.com.au/public/rss/2.0/dtele_lifestyle_227.xml'), 
                      (u'Music', u'http://feeds.news.com.au/public/rss/2.0/dtele_music_441.xml'), 
                      (u'Property Confidential', u'http://feeds.news.com.au/public/rss/2.0/dtele_property_confidential_463.xml'), 
                      (u'Property - Your Space', u'http://feeds.news.com.au/public/rss/2.0/dtele_property_yourspace_462.xml'), 
                      (u'Confidential News', u'http://feeds.news.com.au/public/rss/2.0/dtele_entertainment_confidential_252.xml'), 
                      (u'Confidential Biographies', u'http://feeds.news.com.au/public/rss/2.0/dtele_confidential_biographies_491.xml'), 
                      (u'Confidential Galleries', u'http://feeds.news.com.au/public/rss/2.0/dtele_confidential_galleries_483.xml'), 
                      (u'Confidential In-depth', u'http://feeds.news.com.au/public/rss/2.0/dtele_confidential_indepth_490.xml'), 
                      (u'Confidential ShowBuzz', u'http://feeds.news.com.au/public/rss/2.0/dtele_confidential_showbuzz_485.xml'), 
                      (u'Sport', u'http://feeds.news.com.au/public/rss/2.0/dtele_sport_203.xml'), 
                      (u'AFL', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_afl_341.xml'), 
                      (u'Cricket', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_cricket_343.xml'), 
                      (u'Horse Racing', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_horseracing_686.xml'), 
                      (u'NRL', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_nrl_345.xml'), 
                      (u'Rugby Union', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_rugby_union_342.xml'), 
                      (u'Soccer', u'http://feeds.news.com.au/public/rss/2.0/dtele_sports_soccer_344.xml')
                      ]