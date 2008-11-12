#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
lanacion.com.ar
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Lanacion(BasicNewsRecipe):
    title                 = u'La Nacion'
    __author__            = 'Darko Miletic'
    description           = 'Noticias de Argentina y el resto del mundo'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    keep_only_tags = [dict(name='div', attrs={'class':'nota floatFix'})]
    remove_tags = [
                     dict(name='div' , attrs={'class':'notaComentario floatFix noprint' })
                    ,dict(name='ul'  , attrs={'class':'cajaHerramientas cajaTop noprint'})
                    ,dict(name='div' , attrs={'class':'cajaHerramientas noprint'        })
                  ]

    feeds          = [  
                         (u'Ultimas noticias'     , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?origen=2'         )
                        ,(u'Diario de hoy'        , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?origen=1'         )
                        ,(u'Politica'             , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=30'  )
                        ,(u'Economia'             , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=272' )
                        ,(u'Deportes'             , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=131' )
                        ,(u'Informacion General'  , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=21'  )
                        ,(u'Cultura'              , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=1'   )
                        ,(u'Opinion'              , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=28'  )
                        ,(u'Espectaculos'         , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=120' )
                        ,(u'Exterior'             , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=7'   )
                        ,(u'Ciencia/Salud'        , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=498' )
                        ,(u'Revista'              , u'http://www.lanacion.com.ar/herramientas/rss/index.asp?categoria_id=494' )
                     ]
