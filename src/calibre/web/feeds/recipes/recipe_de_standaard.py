__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
standaard.be
'''

from calibre.web.feeds.news import BasicNewsRecipe

class DeStandaard(BasicNewsRecipe):
    title                 = u'De Standaard'
    __author__            = u'Darko Miletic'
    language = _('French')
    description           = u'News from Belgium'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    keep_only_tags    = [dict(name='div' , attrs={'id':'_parts_midContainer_div'})]
    remove_tags_after  = dict(name='h3', attrs={'title':'Binnenland'})
    remove_tags = [
                     dict(name='h3'  , attrs={'title':'Binnenland'   })
                    ,dict(name='p'   , attrs={'class':'by'           })
                    ,dict(name='div' , attrs={'class':'articlesright'})
                    ,dict(name='a'   , attrs={'class':'help'         })
                    ,dict(name='a'   , attrs={'class':'archive'      })
                    ,dict(name='a'   , attrs={'class':'print'        })
                    ,dict(name='a'   , attrs={'class':'email'        })
                  ]
    
    feeds          = [  
                       (u'De Standaard Online', u'http://feeds.feedburner.com/dso-front')
                     ]
