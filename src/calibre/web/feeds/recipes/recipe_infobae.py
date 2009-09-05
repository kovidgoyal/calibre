#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
infobae.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Infobae(BasicNewsRecipe):
    title                 = 'Infobae.com'
    __author__            = 'Darko Miletic'
    description           = 'Informacion Libre las 24 horas'
    publisher             = 'Infobae.com'
    category              = 'news, politics, Argentina'     
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    language = 'es'

    encoding              = 'cp1252'
    cover_url             = 'http://www.infobae.com/imgs/header/header.gif'
    remove_javascript     = True
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        , '--ignore-colors'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    remove_tags = [
                     dict(name=['embed','link','object'])
                    ,dict(name='a', attrs={'onclick':'javascript:window.print()'})
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

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n<meta http-equiv="Content-Language" content="es-AR"/>\n'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
