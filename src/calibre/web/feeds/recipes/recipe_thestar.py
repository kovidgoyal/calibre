#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.thestar.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheTorontoStar(BasicNewsRecipe):
    title                 = 'The Toronto Star'
    __author__            = 'Darko Miletic'
    description           = "Canada's largest daily newspaper"
    oldest_article        = 2
    language              = 'en_CA'
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    publisher             = 'The Toronto Star'
    category              = "Toronto Star,Canada's largest daily newspaper,breaking news,classifieds,careers,GTA,Toronto Maple Leafs,sports,Toronto,news,editorial,The Star,Ontario,information,columnists,business,entertainment,births,deaths,automotive,rentals,weather,archives,Torstar,technology,Joseph Atkinson"
    encoding              = 'utf-8'
    extra_css             = ' .headlineArticle{font-size: x-large; font-weight: bold} .navbar{text-align:center} '

    conversion_options = {
                             'comments'    : description
                            ,'tags'        : category
                            ,'publisher'   : publisher
                         }

    keep_only_tags = [dict(name='div', attrs={'id':'AssetWebPart1'})]
    remove_attributes= ['style']

    feeds          = [
                        (u'News'         , u'http://www.thestar.com/rss/0?searchMode=Query&categories=296'    )
                       ,(u'Opinions'     , u'http://www.thestar.com/rss/0?searchMode=Query&categories=311'    )
                       ,(u'Business'     , u'http://www.thestar.com/rss/0?searchMode=Query&categories=294'    )
                       ,(u'Sports'       , u'http://www.thestar.com/rss/0?searchMode=Query&categories=295'    )
                       ,(u'Entertainment', u'http://www.thestar.com/rss/0?searchMode=Query&categories=296'    )
                       ,(u'Living'       , u'http://www.thestar.com/rss/0?searchMode=Query&categories=296'    )
                       ,(u'Travel'       , u'http://www.thestar.com/rss/82858?searchMode=Lineup'              )
                       ,(u'Science'      , u'http://www.thestar.com/rss/82848?searchMode=Query&categories=300')
                     ]

    def print_version(self, url):
        return url.replace('/article/','/printArticle/')

