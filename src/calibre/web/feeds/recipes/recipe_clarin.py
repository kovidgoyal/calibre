#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
clarin.com
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Clarin(BasicNewsRecipe):
    title                 = 'Clarin'
    __author__            = 'Darko Miletic'
    description           = 'Noticias de Argentina y mundo'
    publisher             = 'Grupo Clarin'
    category              = 'news, politics, Argentina'
    oldest_article        = 2
    max_articles_per_feed = 100
    use_embedded_content  = False
    no_stylesheets        = True
    cover_url             = strftime('http://www.clarin.com/diario/%Y/%m/%d/portada.jpg')
    remove_javascript     = True
    encoding              = 'cp1252'
    language = 'es'

    lang                  = 'es-AR'
    direction             = 'ltr'
    extra_css             = ' .Txt{ font-family: sans-serif } .Volan{ font-family: sans-serif; font-size: x-small} .Pie{ font-family: sans-serif; font-size: x-small} .Copete{font-family: sans-serif; font-size: large} .Hora{font-family: sans-serif; font-size: large} .Autor{font-family: sans-serif; font-size: small} '

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\npretty_print=True\noverride_css=" p {text-indent: 0cm; margin-top: 0em; margin-bottom: 0.5em} "'

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

    def print_version(self, url):
        rest  = url.partition('-0')[-1]
        lmain = rest.partition('.')[0]
        lurl = u'http://www.servicios.clarin.com/notas/jsp/clarin/v9/notas/imprimir.jsp?pagid=' + lmain
        return lurl

    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

