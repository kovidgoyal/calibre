#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
infobae.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Infobae(BasicNewsRecipe):
    title                 = 'Infobae.com'
    __author__            = 'Darko Miletic'
    description           = 'Informacion Libre las 24 horas'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'iso-8859-1'
    cover_url             = 'http://www.infobae.com/imgs/header/header.gif'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Argentina'
                        , '--publisher'     , 'Infobae.com'
                        ]


    
    feeds = [
              (u'Noticias'  , u'http://www.infobae.com/adjuntos/html/RSS/hoy.xml'       )
             ,(u'Salud'     , u'http://www.infobae.com/adjuntos/html/RSS/salud.xml'     )
             ,(u'Tecnologia', u'http://www.infobae.com/adjuntos/html/RSS/tecnologia.xml')
             ,(u'Deportes'  , u'http://www.infobae.com/adjuntos/html/RSS/deportes.xml'  )
            ]

    def print_version(self, url):
        main, sep, article_part = url.partition('contenidos/')
        article_id, rsep, rrest = article_part.partition('-')
        return u'http://www.infobae.com/notas/nota_imprimir.php?Idx=' + article_id
