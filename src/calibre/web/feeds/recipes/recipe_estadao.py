#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
estadao.com.br
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Estadao(BasicNewsRecipe):
    title                 = 'O Estado de S. Paulo'
    __author__            = 'Darko Miletic'
    description           = 'News from Brasil in Portuguese'
    publisher             = 'O Estado de S. Paulo'
    category              = 'news, politics, Brasil'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf8'
    cover_url             = 'http://www.estadao.com.br/img/logo_estadao.png'
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'id':'c1'})]

    remove_tags = [
                     dict(name=['script','object','form','ul'])
                    ,dict(name='div', attrs={'id':['votacao','estadaohoje']})
                    ,dict(name='p', attrs={'id':'ctrl_texto'})
                    ,dict(name='p', attrs={'class':'texto'})
                  ]

    feeds = [
               (u'Manchetes Estadao', u'http://www.estadao.com.br/rss/manchetes.xml')
              ,(u'Ultimas noticias', u'http://www.estadao.com.br/rss/ultimas.xml')
              ,(u'Nacional', u'http://www.estadao.com.br/rss/nacional.xml')
              ,(u'Internacional', u'http://www.estadao.com.br/rss/internacional.xml')
              ,(u'Cidades', u'http://www.estadao.com.br/rss/cidades.xml')
              ,(u'Esportes', u'http://www.estadao.com.br/rss/esportes.xml')
              ,(u'Arte & Lazer', u'http://www.estadao.com.br/rss/arteelazer.xml')
              ,(u'Economia', u'http://www.estadao.com.br/rss/economia.xml')
              ,(u'Vida &', u'http://www.estadao.com.br/rss/vidae.xml')
            ]

    def preprocess_html(self, soup):
        ifr = soup.find('iframe')
        if ifr:
           ifr.extract()
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = 'pt'

