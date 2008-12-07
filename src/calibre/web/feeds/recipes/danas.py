#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
danas.rs
'''
import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Danas(BasicNewsRecipe):
    title                 = u'Danas'
    __author__            = 'Darko Miletic'
    description           = 'Vesti'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [ dict(name='div', attrs={'id':'left'}) ]
    remove_tags_after  = dict(name='div', attrs={'id':'comments'})
    remove_tags = [
                     dict(name='div', attrs={'class':'width_1_4'})
                    ,dict(name='div', attrs={'class':'metaClanka'})
                    ,dict(name='div', attrs={'id':'comments'})
                    ,dict(name='div', attrs={'class':'baner'})
                  ]



    feeds          = [ (u'Vesti', u'http://www.danas.rs/rss/rss.asp')]
