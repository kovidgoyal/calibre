#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
www.heise.de/tp
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Telepolis(BasicNewsRecipe):
    title                 = 'Telepolis'
    __author__            = 'Darko Miletic'
    description           = 'News from Germany in German'
    oldest_article        = 2
    max_articles_per_feed = 100
    language = _('German')
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    
    html2lrf_options = [  '--comment'       , description
                        , '--category'      , 'blog,news'
                       ]

    keep_only_tags = [
                       dict(name='table', attrs={'class':'inhalt-table'})
                      ,dict(name='table', attrs={'class':'blogtable'   })
                     ]
    remove_tags = [
                     dict(name='table', attrs={'class':'img'    })
                    ,dict(name='img'  , attrs={'src':'/tp/r4/icons/inline/extlink.gif'})
                  ]

    feeds       = [(u'Telepolis Newsfeed', u'http://www.heise.de/tp/news.rdf')]
