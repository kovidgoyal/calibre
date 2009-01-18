#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
clarin.com
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class Clarin(BasicNewsRecipe):
    title                 = 'Clarin'
    __author__            = 'Darko Miletic'
    description           = 'Noticias de Argentina y mundo'
    oldest_article        = 2
    max_articles_per_feed = 100
    use_embedded_content  = False
    no_stylesheets        = True
    cover_url             = strftime('http://www.clarin.com/diario/%Y/%m/%d/portada.jpg')
    
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Argentina'
                        , '--publisher', 'Grupo Clarin'
                        ]
    
    remove_tags = [
                     dict(name='a'   , attrs={'class':'Imp'   })
                    ,dict(name='div' , attrs={'class':'Perma' })
                    ,dict(name='h1'  , text='Imprimir'         )
                  ]
    
    feeds = [ 
               (u'Ultimo Momento', u'http://www.clarin.com/diario/hoy/um/sumariorss.xml') 
              ,(u'El Pais'       , u'http://www.clarin.com/diario/hoy/elpais.xml'       ) 
              ,(u'Opinion'       , u'http://www.clarin.com/diario/hoy/opinion.xml'      ) 
              ,(u'El Mundo'      , u'http://www.clarin.com/diario/hoy/elmundo.xml'      ) 
              ,(u'Sociedad'      , u'http://www.clarin.com/diario/hoy/sociedad.xml'     ) 
              ,(u'La Ciudad'     , u'http://www.clarin.com/diario/hoy/laciudad.xml'     ) 
              ,(u'Policiales'    , u'http://www.clarin.com/diario/hoy/policiales.xml'   )
              ,(u'Deportes'      , u'http://www.clarin.com/diario/hoy/deportes.xml'     )              
            ]
    
    def get_article_url(self, article):
        artl  = article.get('link',  None)
        rest  = artl.partition('-0')[-1]
        lmain = rest.partition('.')[0]
        return 'http://www.servicios.clarin.com/notas/jsp/clarin/v9/notas/imprimir.jsp?pagid=' + lmain
        
