#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
lacuarta.cl
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LaCuarta(BasicNewsRecipe):
    title                 = 'La Cuarta'
    __author__            = 'Darko Miletic'
    description           = 'El sitio de noticias online de Chile'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Chile'
                        , '--publisher'     , title
                        ]
                        
    keep_only_tags = [dict(name='div', attrs={'class':'articulo desplegado'}) ]

    remove_tags = [  
                     dict(name='script')
                    ,dict(name='ul')
                    ,dict(name='div', attrs={'id':['toolbox','articleImageDisplayer','enviarAmigo']})
                    ,dict(name='div', attrs={'class':['par ad-1','par ad-2']})
                    ,dict(name='input')
                    ,dict(name='p', attrs={'id':['mensajeError','mensajeEnviandoNoticia','mensajeExito']})
                    ,dict(name='strong', text='PUBLICIDAD')
                  ]

    
    feeds = [(u'Noticias', u'http://lacuarta.cl/app/rss?sc=TEFDVUFSVEE=')]

    
