#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
juventudrebelde.cu
'''
from calibre import strftime

from calibre.web.feeds.news import BasicNewsRecipe

class Juventudrebelde(BasicNewsRecipe):
    title                 = 'Juventud Rebelde'
    __author__            = 'Darko Miletic'
    description           = 'Diario de la Juventud Cubana'    
    oldest_article        = 2
    language = _('Spanish')
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = strftime('http://www.juventudrebelde.cu/UserFiles/File/impreso/iportada-%Y-%m-%d.jpg')

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Cuba'
                        , '--publisher'     , title
                        , '--ignore-tables'
                        ]

    keep_only_tags = [dict(name='div', attrs={'id':'noticia'})]

    feeds = [
               (u'Generales', u'http://www.juventudrebelde.cu/rss/generales.php' )
              ,(u'Cuba', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=cuba' )
              ,(u'Internacionales', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=internacionales' )
              ,(u'Opinion', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=opinion' )
              ,(u'Cultura', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=cultura' )
              ,(u'Deportes', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=deportes' )
              ,(u'Lectura', u'http://www.juventudrebelde.cu/rss/generales.php?seccion=lectura' )
            ]

            
