#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
elmundo.es
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ElMundo(BasicNewsRecipe):
    title                 = 'El Mundo'
    __author__            = 'Darko Miletic'
    description           = 'News from Spain'
    publisher             = 'El Mundo'
    category              = 'news, politics, Spain'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'iso8859_15'
    cover_url             = 'http://estaticos02.cache.el-mundo.net/papel/imagenes/v2.0/logoverde.gif'
    remove_javascript     = True
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 


    keep_only_tags = [
                        dict(name='div', attrs={'id':['bloqueprincipal','noticia']})
                       ,dict(name='div', attrs={'class':['contenido_noticia_01']})
                     ]
    remove_tags = [
                     dict(name='div', attrs={'class':['herramientas','publicidad_google']})
                    ,dict(name='div', attrs={'id':'modulo_multimedia' })
                    ,dict(name='ul', attrs={'class':'herramientas' })                                         
                    ,dict(name=['object','link'])
                  ]
                            
    feeds = [ 
              (u'Portada'         , u'http://rss.elmundo.es/rss/descarga.htm?data2=4' )
             ,(u'Espana'          , u'http://rss.elmundo.es/rss/descarga.htm?data2=8' )
             ,(u'Internacional'   , u'http://rss.elmundo.es/rss/descarga.htm?data2=9' )
             ,(u'Cultura'         , u'http://rss.elmundo.es/rss/descarga.htm?data2=6' )
             ,(u'Ciencia/Ecologia', u'http://rss.elmundo.es/rss/descarga.htm?data2=5' )
             ,(u'Comunicacion'    , u'http://rss.elmundo.es/rss/descarga.htm?data2=26')
             ,(u'Television'      , u'http://rss.elmundo.es/rss/descarga.htm?data2=76')
            ]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = 'es'
