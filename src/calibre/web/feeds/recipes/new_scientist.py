#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
newscientist.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class NewScientist(BasicNewsRecipe):
    title                 = u'New Scientist'
    __author__            = 'Darko Miletic'
    description           = 'Science news'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    
    keep_only_tags = [
                        dict(name='div'  , attrs={'id':'pgtop'   })
                       ,dict(name='div'  , attrs={'id':'maincol' })
                     ]
    remove_tags = [
                     dict(name='div'  , attrs={'class':'hldBd' })
                    ,dict(name='div'  , attrs={'id':'compnl' })
                    ,dict(name='div'  , attrs={'id':'artIssueInfo' })
                  ]

    feeds          = [
                        (u'Latest Headlines' , u'http://feeds.newscientist.com/science-news'              )
                       ,(u'Magazine'         , u'http://www.newscientist.com/feed/magazine'               )                      
                       ,(u'Health'           , u'http://www.newscientist.com/feed/view?id=2&type=channel' )
                       ,(u'Life'             , u'http://www.newscientist.com/feed/view?id=3&type=channel' )
                       ,(u'Space'            , u'http://www.newscientist.com/feed/view?id=6&type=channel' )
                     ]