#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
fudzilla.com
'''

import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Fudzilla(BasicNewsRecipe):
    title                 = u'Fudzilla'
    __author__            = 'Darko Miletic'
    language = 'en'

    description           = 'Tech news'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    feeds = [ (u'Posts', u'http://www.fudzilla.com/index.php?option=com_rss&feed=RSS2.0&no_html=1')]

    def print_version(self, url):
        nurl = url.replace('http://www.fudzilla.com/index.php','http://www.fudzilla.com/index2.php')
        nmain, nsep, nrest = nurl.partition('&Itemid=')
        return  nmain + '&pop=1&page=0&Itemid=1'
