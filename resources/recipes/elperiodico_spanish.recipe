#!/usr/bin/env  python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
elperiodico.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class ElPeriodico_esp(BasicNewsRecipe):
    title                 = 'El Periodico de Catalunya'
    __author__            = 'Darko Miletic'
    description           = 'Noticias desde Catalunya'
    publisher             = 'elperiodico.com'
    category              = 'news, politics, Spain, Catalunya'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    delay                 = 1
    encoding              = 'cp1252'
    language = 'es'


    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    feeds              = [(u"Toda la edición", u'http://www.elperiodico.com/rss.asp?id=46')]


    keep_only_tags = [dict(name='div', attrs={'id':'noticia'})]

    remove_tags        = [
                              dict(name=['object','link','script'])
                             ,dict(name='ul',attrs={'class':'herramientasDeNoticia'})
                             ,dict(name='div', attrs={'id':'inferiores'})
                         ]

    def print_version(self, url):
        return url.replace('/default.asp?','/print.asp?')

    def preprocess_html(self, soup):
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

