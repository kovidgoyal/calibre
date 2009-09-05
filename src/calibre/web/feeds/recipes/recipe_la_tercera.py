#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
latercera.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LaTercera(BasicNewsRecipe):
    title                 = 'La Tercera'
    __author__            = 'Darko Miletic'
    description           = 'El sitio de noticias online de Chile'
    publisher             = 'La Tercera'
    category              = 'news, politics, Chile'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'cp1252'
    remove_javascript     = True
    use_embedded_content  = False
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
                        
    keep_only_tags = [dict(name='div', attrs={'class':['span-16 articulo border','span-16 border','span-16']}) ]

    remove_tags = [  
                     dict(name='script')
                    ,dict(name='ul')
                    ,dict(name='div', attrs={'id':['boxComentarios','shim','enviarAmigo']})
                    ,dict(name='div', attrs={'class':['ad640','span-10 imgSet A','infoRelCol']})
                    ,dict(name='input')
                    ,dict(name='p', attrs={'id':['mensajeError','mensajeEnviandoNoticia','mensajeExito']})
                  ]

    
    feeds = [ 
               (u'Noticias de ultima hora', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&ul=1')
              ,(u'Pais', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=654')
              ,(u'Mundo', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=678')
              ,(u'Deportes', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=656')
              ,(u'Negocios', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=655')
              ,(u'Entretenimiento', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=661')
              ,(u'Motores', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=665')
              ,(u'Tendencias', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=659')
              ,(u'Estilo', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=660')
              ,(u'Educacion', u'http://www.latercera.com/app/rss?sc=TEFURVJDRVJB&category=657')
            ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CL"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
    
    language = 'es'
