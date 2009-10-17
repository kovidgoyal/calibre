#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
sfgate.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class SanFranciscoChronicle(BasicNewsRecipe):
    title                 = u'San Francisco Chronicle'
    __author__            = u'Darko Miletic'
    description           = u'San Francisco news'
    language = 'en'

    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    remove_tags_before = {'class':'articleheadings'}
    remove_tags_after =  dict(name='div', attrs={'id':'articlecontent' })
    remove_tags = [
                     dict(name='div', attrs={'class':'tools tools_top'})
                    ,dict(name='div', attrs={'id':'articlebox'        })
                  ]

    feeds          = [
                         (u'Top News Stories', u'http://www.sfgate.com/rss/feeds/news.xml')
                     ]
