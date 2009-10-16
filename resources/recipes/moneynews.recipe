#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
moneynews.newsmax.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class MoneyNews(BasicNewsRecipe):
    title                 = 'Moneynews.com'
    __author__            = 'Darko Miletic'
    description           = 'Financial news worldwide'
    publisher             = 'moneynews.com'
    language = 'en'

    category              = 'news, finances, USA, business'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    feeds = [
              (u'Street Talk'          , u'http://moneynews.newsmax.com/xml/streettalk.xml'  )
             ,(u'Finance News'         , u'http://moneynews.newsmax.com/xml/FinanceNews.xml' )
             ,(u'Economy'              , u'http://moneynews.newsmax.com/xml/economy.xml'     )
             ,(u'Companies'            , u'http://moneynews.newsmax.com/xml/companies.xml'   )
             ,(u'Markets'              , u'http://moneynews.newsmax.com/xml/Markets.xml'     )
             ,(u'Investing & Analysis' , u'http://moneynews.newsmax.com/xml/investing.xml'   )
            ]


    keep_only_tags = [dict(name='table', attrs={'class':'copy'})]

    remove_tags = [
                     dict(name='td'   , attrs={'id':'article_fontsize'})
                    ,dict(name='table', attrs={'id':'toolbox'         })
                    ,dict(name='tr'   , attrs={'id':'noprint3'        })
                  ]

