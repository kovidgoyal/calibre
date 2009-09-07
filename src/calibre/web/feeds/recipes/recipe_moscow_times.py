#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
moscowtimes.ru
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Moscowtimes(BasicNewsRecipe):
    title                 = u'The Moscow Times'
    __author__            = 'Darko Miletic'
    description           = 'News from Russia'
    language = 'en'
    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    feeds          = [
                        (u'The Moscow Times'     , u'http://www.themoscowtimes.com/rss.xml'     )
                     ]

    def print_version(self, url):
        return url + '&print=Y'