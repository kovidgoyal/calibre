#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.hln.be
'''

from calibre.web.feeds.news import BasicNewsRecipe

class HLN_be(BasicNewsRecipe):
    title                 = 'HLN Belgium'
    __author__            = 'Darko Miletic'
    description           = 'Belgium news'
    publisher             = 'HLN'
    category              = 'news, politics, Belgium'
    oldest_article        = 2
    max_articles_per_feed = 100
    use_embedded_content  = False
    no_stylesheets        = True
    encoding              = 'utf-8'
    language = 'nl'

    
    conversion_options = {  
                             'comments'    : description
                            ,'tags'        : category
                            ,'language'    : 'nl-NL'
                            ,'publisher'   : publisher
                         }
    
    remove_tags = [dict(name=['form','object','embed'])]

    keep_only_tags = [dict(name='div', attrs={'id':'art_box2'})]

    feeds = [(u'Articles', u'http://www.hln.be/rss.xml')]
