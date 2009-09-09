#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
emol.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ElMercurio(BasicNewsRecipe):
    title                 = 'El Mercurio online'
    __author__            = 'Darko Miletic'
    description           = 'El sitio de noticias online de Chile'
    publisher             = 'El Mercurio'
    category              = 'news, politics, Chile'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.emol.com/especiales/logo_emol/logo_emol.gif'
    remove_javascript     = True
    use_embedded_content  = False

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [
                        dict(name='div', attrs={'class':'despliegue-txt_750px'})
                       ,dict(name='div', attrs={'id':'div_cuerpo_participa'})
                     ]

    remove_tags = [
                     dict(name='div', attrs={'class':'contenedor_despliegue-col-left300'})
                    ,dict(name='div', attrs={'id':['div_centro_dn_opc','div_cabezera','div_secciones','div_contenidos','div_pie','nav']})
                    ]

    feeds = [
               (u'Noticias de ultima hora', u'http://www.emol.com/rss20/rss.asp?canal=0')
              ,(u'Nacional', u'http://www.emol.com/rss20/rss.asp?canal=1')
              ,(u'Mundo', u'http://www.emol.com/rss20/rss.asp?canal=2')
              ,(u'Deportes', u'http://www.emol.com/rss20/rss.asp?canal=4')
              ,(u'Magazine', u'http://www.emol.com/rss20/rss.asp?canal=6')
              ,(u'Tecnologia', u'http://www.emol.com/rss20/rss.asp?canal=5')
              ,(u'La Musica', u'http://www.emol.com/rss20/rss.asp?canal=7')
            ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CL"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = 'es'
