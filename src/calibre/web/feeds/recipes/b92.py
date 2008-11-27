#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
b92.net
'''
import locale
from calibre.web.feeds.news import BasicNewsRecipe

class B92(BasicNewsRecipe):
    title                 = u'B92'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne vesti iz Srbije i sveta'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    remove_tags_after  = dict(name='div', attrs={'class':'gas'})
    remove_tags = [
                     dict(name='div'  , attrs={'class':'interaction clearfix' })
                    ,dict(name='div'  , attrs={'class':'gas'                  })
                    ,dict(name='ul'   , attrs={'class':'comment-nav'          })
                    ,dict(name='table', attrs={'class':'pages-navigation-form'})
                  ]

    feeds          = [
                        (u'Vesti'     , u'http://www.b92.net/info/rss/vesti.xml'     )
                       ,(u'Kultura'   , u'http://www.b92.net/info/rss/kultura.xml'   )                      
                       ,(u'Automobili', u'http://www.b92.net/info/rss/automobili.xml')                      
                       ,(u'Zivot'     , u'http://www.b92.net/info/rss/zivot.xml'     )
                       ,(u'Tehnopolis', u'http://www.b92.net/info/rss/tehnopolis.xml')
                       ,(u'Biz'       , u'http://www.b92.net/info/rss/biz.xml'       )
                     ]

    def print_version(self, url):
        return url + '&version=print'
