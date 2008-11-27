#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
blic.rs
'''
import locale
from calibre.web.feeds.news import BasicNewsRecipe

class Blic(BasicNewsRecipe):
    title                 = u'Blic'
    __author__            = 'Darko Miletic'
    description           = 'Vesti'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 

    keep_only_tags = [ dict(name='div', attrs={'class':'single_news'}) ]

    feeds          = [ (u'Vesti', u'http://www.blic.rs/rssall.php')]

    def print_version(self, url):
        start_url, question, rest_url = url.partition('?')
        return u'http://www.blic.rs/_print.php?' + rest_url
