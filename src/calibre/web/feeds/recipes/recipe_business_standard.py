#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.business-standard.com
'''

from calibre.web.feeds.recipes import BasicNewsRecipe

class BusinessStandard(BasicNewsRecipe):
    title                  = 'Business Standard'
    __author__             = 'Darko Miletic'
    description            = "India's most respected business daily"
    oldest_article         = 7
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    encoding               = 'cp1252'
    publisher              = 'Business Standard Limited'
    category               = 'news, business, money, india, world'
    language               = 'en_IN'
    
    conversion_options = {  
                             'comments'        : description
                            ,'tags'            : category
                            ,'language'        : language
                            ,'publisher'       : publisher
                            ,'linearize_tables': True
                         }
    
    remove_attributes=['style']
    remove_tags = [dict(name=['object','link','script','iframe'])]
    
    feeds = [
               (u'News Now'            , u'http://feeds.business-standard.com/News-Now.xml'              )
              ,(u'Banking & finance'   , u'http://feeds.business-standard.com/Banking-Finance-All.xml'   )
              ,(u'Companies & Industry', u'http://feeds.business-standard.com/Companies-Industry-All.xml')
              ,(u'Economy & Policy'    , u'http://feeds.business-standard.com/Economy-Policy-All.xml'    )
              ,(u'Tech World'          , u'http://feeds.business-standard.com/Tech-World-All.xml'        )
              ,(u'Life & Leisure'      , u'http://feeds.business-standard.com/Life-Leisure-All.xml'      )
              ,(u'Markets & Investing' , u'http://feeds.business-standard.com/Markets-Investing-All.xml' )
              ,(u'Management & Mktg'   , u'http://feeds.business-standard.com/Management-Mktg-All.xml'   )
              ,(u'Automobiles'         , u'http://feeds.business-standard.com/Automobiles.xml'           )
              ,(u'Aviation'            , u'http://feeds.business-standard.com/Aviation.xml'              )
            ]

    def print_version(self, url):
        autono  = url.rpartition('autono=')[2]
        tp = 'on'
        hk = url.rpartition('bKeyFlag=')[1]
        if  hk == '':
           tp = ''
        return 'http://www.business-standard.com/india/printpage.php?autono=' + autono + '&tp=' + tp

    def get_article_url(self, article):
        return article.get('guid',  None)
