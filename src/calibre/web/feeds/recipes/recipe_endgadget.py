#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
engadget.com
'''

import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Engadget(BasicNewsRecipe):
    title                 = u'Engadget'
    __author__            = 'Darko Miletic'
    description           = 'Tech news'
    language = 'en'
    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    keep_only_tags     = [ dict(name='div', attrs={'class':'post'}) ]
    remove_tags = [
                      dict(name='object')
                     ,dict(name='div', attrs={'class':'postmeta'})
                     ,dict(name='div', attrs={'class':'quigoads'})
                  ]


    feeds = [ (u'Posts', u'http://www.engadget.com/rss.xml')]

