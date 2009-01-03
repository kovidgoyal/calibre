#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
harpers.org
'''
from calibre.web.feeds.news import BasicNewsRecipe

class Harpers(BasicNewsRecipe):
    title                 = u"Harper's Magazine"
    __author__            = u'Darko Miletic'
    description           = u"Harper's Magazine: Founded June 1850."
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 

    keep_only_tags = [ dict(name='div', attrs={'id':'cached'}) ]
    remove_tags = [
                     dict(name='table', attrs={'class':'rcnt'})
                    ,dict(name='table', attrs={'class':'rcnt topline'})
                  ]

    feeds       = [
                   (u"Harper's Magazine", u'http://www.harpers.org/rss/frontpage-rss20.xml')
                   ]
