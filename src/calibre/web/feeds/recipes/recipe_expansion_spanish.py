#!/usr/bin/env  python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.expansion.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Expansion(BasicNewsRecipe):
    title                 = 'Diario Expansion'
    __author__            = 'Darko Miletic'
    description           = 'Lider de informacion de mercados, economica y politica'
    publisher             = 'expansion.com'
    category              = 'news, politics, Spain'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    delay                 = 1
    encoding              = 'iso-8859-15'
    language = 'es'

    direction             = 'ltr'

    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    feeds              = [
                            (u'Ultimas noticias', u'http://rss.expansion.com/rss/descarga.htm?data2=178')
                           ,(u'Temas del dia'   , u'http://rss.expansion.com/rss/descarga.htm?data2=178')
                         ]


    keep_only_tags = [dict(name='div', attrs={'id':'principal'})]

    remove_tags        = [
                             dict(name=['object','link','script'])
                            ,dict(name='div', attrs={'class':['utilidades','tit_relacionadas']})
                         ]

    remove_tags_after = [dict(name='div', attrs={'class':'tit_relacionadas'})]

    def preprocess_html(self, soup):
        soup.html['dir' ] = self.direction
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

