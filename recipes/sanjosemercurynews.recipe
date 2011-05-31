#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.mercurynews.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class MercuryNews(BasicNewsRecipe):
    title                 = 'San Jose Mercury News'
    __author__            = 'Darko Miletic'
    description           = 'News from San Jose'
    publisher             = 'San Jose Mercury News'
    category              = 'news, politics, USA, San Jose, California'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    language              = 'en'

    conversion_options = {
                          'comment'   : description
                        , 'tags'      : category
                        , 'publisher' : publisher
                        , 'language'  : language
                        }

    keep_only_tags    =[
                         dict(name='h1', attrs={'id':'articleTitle'})
                         ,dict(name='div', attrs={'id':'articleBody'})
                       ]
    remove_tags = [
                      dict(name='div',attrs={'class':'articleEmbeddedAdBox'})
                     ,dict(name=['link','iframe','object'])
                     ,dict(name='div',attrs={'id':'articleViewerGroup'})
                  ]

    feeds = [
              (u'News'      , u'http://feeds.mercurynews.com/mngi/rss/CustomRssServlet/568/200735.xml')
             ,(u'Politics'  , u'http://feeds.mercurynews.com/mngi/rss/CustomRssServlet/568/200740.xml')
             ,(u'Local News', u'http://feeds.mercurynews.com/mngi/rss/CustomRssServlet/568/200748.xml')
             ,(u'Editorials', u'http://feeds.mercurynews.com/mngi/rss/CustomRssServlet/568/200766.xml')
             ,(u'Opinion'   , u'http://feeds.mercurynews.com/mngi/rss/CustomRssServlet/568/200224.xml')
            ]
