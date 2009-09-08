#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
lasegunda.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LaSegunda(BasicNewsRecipe):
    title                 = 'La Segunda'
    __author__            = 'Darko Miletic'
    description           = 'El sitio de noticias online de Chile' 
    publisher             = 'La Segunda'
    category              = 'news, politics, Chile'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.lasegunda.com/imagenes/logotipo_lasegunda_Oli.gif'
    remove_javascript     = True
    language = 'es'
    
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} "' 
                        
    keep_only_tags = [dict(name='table')]
                        
    feeds = [ 
               (u'Noticias de ultima hora', u'http://www.lasegunda.com/rss20/index.asp?canal=0')
              ,(u'Politica', u'http://www.lasegunda.com/rss20/index.asp?canal=21')
              ,(u'Cronica', u'http://www.lasegunda.com/rss20/index.asp?canal=20')
              ,(u'Internacional', u'http://www.lasegunda.com/rss20/index.asp?canal=23')
              ,(u'Deportes', u'http://www.lasegunda.com/rss20/index.asp?canal=24')
              ,(u'Epectaculos/Cultura', u'http://www.lasegunda.com/rss20/index.asp?canal=25')
              ,(u'Educacion', u'http://www.lasegunda.com/rss20/index.asp?canal=26')
              ,(u'Ciencia y Tecnologia', u'http://www.lasegunda.com/rss20/index.asp?canal=27')
              ,(u'Solidaridad', u'http://www.lasegunda.com/rss20/index.asp?canal=28')
              ,(u'Buena Vida', u'http://www.lasegunda.com/rss20/index.asp?canal=32')
            ]

    def print_version(self, url):
        rest, sep, article_id = url.partition('index.asp?idnoticia=')        
        return u'http://www.lasegunda.com/edicionOnline/include/secciones/_detalle_impresion.asp?idnoticia=' + article_id

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CL"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup
    
