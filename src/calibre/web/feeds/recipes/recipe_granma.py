#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
granma.cubaweb.cu
'''
import urllib


from calibre.web.feeds.news import BasicNewsRecipe

class Granma(BasicNewsRecipe):
    title                 = 'Diario Granma'
    __author__            = 'Darko Miletic'
    language = _('Spanish')
    description           = 'Organo oficial del Comite Central del Partido Comunista de Cuba'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://www.granma.cubaweb.cu/imagenes/granweb229d.jpg'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Cuba'
                        , '--publisher'     , title
                        , '--ignore-tables'
                        ]

    keep_only_tags = [dict(name='table', attrs={'height':'466'})]

    feeds = [(u'Noticias', u'http://www.granma.cubaweb.cu/noticias.xml' )]

    
    def preprocess_html(self, soup):
        del soup.body.table['style']
        rtag = soup.find('td', attrs={'height':'458'})
        if rtag:
            del rtag['style']
        return soup
    
