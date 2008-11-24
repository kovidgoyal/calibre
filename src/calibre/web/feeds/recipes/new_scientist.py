#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
newscientist.com
'''
#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>, AprilHare'
'''
newscientist.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class NewScientist(BasicNewsRecipe):
    title                 = u'New Scientist - Online News'
    __author__            = 'Darko Miletic'
    description           = 'News from Science'
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
                       ,(u'Physics and Mathematics'            , u'http://www.newscientist.com/feed/view?id=4&type=channel' )
                       ,(u'Environment'            , u'http://www.newscientist.com/feed/view?id=1&type=channel' )
                       ,(u'Science in Society'            , u'http://www.newscientist.com/feed/view?id=5&type=channel' )
                       ,(u'Tech'            , u'http://www.newscientist.com/feed/view?id=7&type=channel' )
                     ]