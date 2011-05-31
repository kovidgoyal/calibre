#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
japantimes.co.jp
'''

from calibre.web.feeds.news import BasicNewsRecipe

class JapanTimes(BasicNewsRecipe):
    title                 = u'The Japan Times'
    __author__            = 'Darko Miletic'
    description           = 'News from Japan'
    language = 'en'
    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    keep_only_tags    = [ dict(name='div', attrs={'id':'searchresult'}) ]
    remove_tags_after = [ dict(name='div', attrs={'id':'mainbody'    }) ]
    remove_tags       = [
                           dict(name='div'  , attrs={'id':'ads' })
                          ,dict(name='table', attrs={'width':470})
                        ]


    feeds          = [
                        (u'The Japan Times', u'http://feedproxy.google.com/japantimes')
                     ]