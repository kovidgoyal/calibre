#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.torontosun.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TorontoSun(BasicNewsRecipe):
    title                 = 'Toronto SUN'
    __author__            = 'Darko Miletic'
    description           = 'News from Canada'
    publisher             = 'Toronto Sun'
    category              = 'news, politics, Canada'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    language              = 'en_CA'

    conversion_options = {
                          'comment'   : description
                        , 'tags'      : category
                        , 'publisher' : publisher
                        , 'language'  : language
                        }

    keep_only_tags    =[
                         dict(name='div', attrs={'class':'articleHead'})
                         ,dict(name='div', attrs={'id':'channelContent'})
                       ]
    remove_tags = [
                      dict(name='div',attrs={'class':['leftBox','bottomBox clear','bottomBox','breadCrumb']})
                     ,dict(name=['link','iframe','object'])
                     ,dict(name='a',attrs={'rel':'swap'})
                     ,dict(name='ul',attrs={'class':'tabs dl contentSwap'})
                  ]

    remove_tags_after = dict(name='div',attrs={'class':'bottomBox clear'})

    feeds = [
              (u'News'       , u'http://www.torontosun.com/news/rss.xml'           )
             ,(u'Canada'     , u'http://www.torontosun.com/news/canada/rss.xml'    )
             ,(u'Columnists' , u'http://www.torontosun.com/news/columnists/rss.xml')
             ,(u'World'      , u'http://www.torontosun.com/news/world/rss.xml'     )
             ,(u'Money'      , u'http://www.torontosun.com/money/rss.xml'          )
            ]
