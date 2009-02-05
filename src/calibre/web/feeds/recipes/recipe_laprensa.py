#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
laprensa.com.ar
'''
import urllib

from calibre.web.feeds.news import BasicNewsRecipe

class LaPrensa(BasicNewsRecipe):
    title                 = 'La Prensa'
    __author__            = 'Darko Miletic'
    description           = 'Informacion Libre las 24 horas'    
    oldest_article        = 7
    language = _('Spanish')
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.laprensa.com.ar/imgs/logo.gif'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Argentina'
                        , '--publisher'     , title
                        ]
                            
    feeds = [ 
              (u'Politica'    , u'http://www.laprensa.com.ar/Rss.aspx?Rss=4' )
             ,(u'Economia'    , u'http://www.laprensa.com.ar/Rss.aspx?Rss=5' )
             ,(u'Opinion'     , u'http://www.laprensa.com.ar/Rss.aspx?Rss=6' )
             ,(u'El Mundo'    , u'http://www.laprensa.com.ar/Rss.aspx?Rss=7' )
             ,(u'Actualidad'  , u'http://www.laprensa.com.ar/Rss.aspx?Rss=8' )
             ,(u'Deportes'    , u'http://www.laprensa.com.ar/Rss.aspx?Rss=9' )
             ,(u'Espectaculos', u'http://www.laprensa.com.ar/Rss.aspx?Rss=10')
            ]

    def print_version(self, url):
        return url.replace('.note.aspx','.NotePrint.note.aspx')

    def get_article_url(self, article):
        raw = article.get('link',  None).encode('utf8')
        final = urllib.quote(raw,':/') 
        return final

    def preprocess_html(self, soup):
        del soup.body['onload']
        return soup
    
