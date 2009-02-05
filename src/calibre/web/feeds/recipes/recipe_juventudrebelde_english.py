#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
juventudrebelde.co.cu
'''
from calibre import strftime

from calibre.web.feeds.news import BasicNewsRecipe

class Juventudrebelde_english(BasicNewsRecipe):
    title                 = 'Juventud Rebelde in english'
    __author__            = 'Darko Miletic'
    description           = 'The newspaper of Cuban Youth'
    language = _('English')    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'iso-8859-1'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Cuba'
                        , '--publisher'     , title
                        , '--ignore-tables'
                        ]

    keep_only_tags = [dict(name='div', attrs={'class':'read'})]

    feeds = [(u'All news', u'http://www.juventudrebelde.cip.cu/rss/all/' )]

            
