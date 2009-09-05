#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
thenation.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class Thenation(BasicNewsRecipe):
    title                 = u'The Nation'
    __author__            = u'Darko Miletic'
    description           = u'Unconventional Wisdom Since 1865'
    oldest_article        = 120
    max_articles_per_feed = 100
    no_stylesheets        = True
    language = 'en'

    use_embedded_content  = False
    simultaneous_downloads = 1
    delay                  = 1
    timefmt                = ' [%A, %d %B, %Y]'
     

    keep_only_tags = [ dict(name='div', attrs={'class':'main'}) ]
    remove_tags = [
                     dict(name='div', attrs={'class':'mod tools'})
                    ,dict(name='div', attrs={'class':'inset'    })
                    ,dict(name='div', attrs={'class':'share'    })
                    ,dict(name='ol' , attrs={'id'   :'comments' })
                    ,dict(name='p'  , attrs={'class':'info'     })
                    ,dict(name='a'  , attrs={'class':'comments' })
                    ,dict(name='ul' , attrs={'class':'important'})
                    ,dict(name='object')
                  ]

    feeds       = [(u"Top Stories", u'http://feedproxy.google.com/TheNationEdPicks')]
