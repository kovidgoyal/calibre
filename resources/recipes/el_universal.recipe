#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
eluniversal.com.mx
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ElUniversal(BasicNewsRecipe):
    title                 = 'El Universal'
    __author__            = 'Darko Miletic'
    description           = 'News from Mexico'
    oldest_article        = 1
    max_articles_per_feed = 100
    publisher             = 'El Universal'
    category              = 'news, politics, Mexico'    
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    remove_javascript     = True
    language = 'es'

    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 

    remove_tags = [dict(name='link')]
                            
    feeds = [ 
              (u'Minuto por Minuto', u'http://www.eluniversal.com.mx/rss/universalmxm.xml' )
             ,(u'Mundo'            , u'http://www.eluniversal.com.mx/rss/mundo.xml'        )
             ,(u'Mexico'           , u'http://www.eluniversal.com.mx/rss/mexico.xml'       )
             ,(u'Estados'          , u'http://www.eluniversal.com.mx/rss/estados.xml'      )
             ,(u'Finanzas'         , u'http://www.eluniversal.com.mx/rss/finanzas.xml'     )
             ,(u'Deportes'         , u'http://www.eluniversal.com.mx/rss/deportes.xml'     )
             ,(u'Espectaculos'     , u'http://www.eluniversal.com.mx/rss/espectaculos.xml' )
             ,(u'Cultura'          , u'http://www.eluniversal.com.mx/rss/cultura.xml'      )
             ,(u'Ciencia'          , u'http://www.eluniversal.com.mx/rss/ciencia.xml'      )
             ,(u'Computacion'      , u'http://www.eluniversal.com.mx/rss/computo.xml'      )
             ,(u'Sociedad'         , u'http://www.eluniversal.com.mx/rss/sociedad.xml'     )
            ]
            
    def print_version(self, url):
        return url.replace('/notas/','/notas/vi_')

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-MX"/><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(font=True):
            del item['font']
        for item in soup.findAll(face=True):
            del item['face']
        for item in soup.findAll(helvetica=True):
            del item['helvetica']
        return soup
        
