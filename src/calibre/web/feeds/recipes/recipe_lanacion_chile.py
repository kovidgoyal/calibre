#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
lanacion.cl
'''
import urllib

from calibre.web.feeds.news import BasicNewsRecipe

class LaNacionChile(BasicNewsRecipe):
    title                 = 'La Nacion Chile'
    __author__            = 'Darko Miletic'
    description           = 'El sitio de noticias online de Chile'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.lanacion.cl/prontus_noticias_v2/imag/site/logo.gif'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Chile'
                        , '--publisher'     , title
                        ]
                        
    keep_only_tags = [dict(name='div', attrs={'class':'bloque'})]
                        
    feeds = [(u'Noticias', u'http://www.lanacion.cl/rss.xml')]

    def print_version(self, url):
        toprint = urllib.quote(url,':/')
        return u'http://www.lanacion.cl/cgi-bx/imprimir.cgi?_URL=' + toprint

    def preprocess_html(self, soup):
        del soup.body['onload']
        soup.head.base.extract()
        item = soup.find('a', attrs={'href':'javascript:window.close()'})
        if item:
           item.extract()
        return soup
    
