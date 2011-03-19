#!/usr/bin/env  python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.marca.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Marca(BasicNewsRecipe):
    title                 = 'Marca'
    __author__            = 'Darko Miletic'
    description           = 'Noticias deportivas'
    publisher             = 'marca.com'
    category              = 'news, sports, Spain'
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

    feeds              = [(u'Portada', u'http://rss.marca.com/rss/descarga.htm?data2=425')]

    keep_only_tags = [dict(name='div', attrs={'class':['cab_articulo','col_izq']})]

    remove_tags        = [
                             dict(name=['object','link','script'])
                            ,dict(name='div', attrs={'class':['colC','peu']})
                            ,dict(name='div', attrs={'class':['utilidades estirar','bloque_int_corr estirar']})
                         ]

    remove_tags_after = [dict(name='div', attrs={'class':'bloque_int_corr estirar'})]

    def preprocess_html(self, soup):
        soup.html['dir' ] = self.direction
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

