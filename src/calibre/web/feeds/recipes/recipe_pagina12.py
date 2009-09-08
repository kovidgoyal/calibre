#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
pagina12.com.ar
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class Pagina12(BasicNewsRecipe):
    title                 = 'Pagina - 12'
    __author__            = 'Darko Miletic'
    description           = 'Noticias de Argentina y el resto del mundo'
    publisher             = 'La Pagina S.A.'
    category              = 'news, politics, Argentina'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'cp1252'
    cover_url             = strftime('http://www.pagina12.com.ar/fotos/%Y%m%d/diario/tapagn.jpg')
    remove_javascript     = True
    use_embedded_content  = False
    language = 'es'



    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'


    remove_tags = [
                     dict(name='div', attrs={'id':'volver'})
                    ,dict(name='div', attrs={'id':'logo'  })
                  ]


    feeds = [(u'Pagina/12', u'http://www.pagina12.com.ar/diario/rss/principal.xml')]

    def print_version(self, url):
        return url.replace('http://www.pagina12.com.ar/','http://www.pagina12.com.ar/imprimir/')

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-AR"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup
