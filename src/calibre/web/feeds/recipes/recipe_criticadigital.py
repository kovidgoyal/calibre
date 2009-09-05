#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
criticadigital.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class CriticaDigital(BasicNewsRecipe):
    title                 = 'Critica de la Argentina'
    __author__            = 'Darko Miletic'
    description           = 'Noticias de Argentina'
    oldest_article        = 2
    max_articles_per_feed = 100
    language = 'es'

    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Argentina'
                        , '--publisher'     , title
                        ]
    
    keep_only_tags = [
                        dict(name='div', attrs={'class':'bloqueTitulosNoticia'})
                       ,dict(name='div', attrs={'id':'c453-1'                 })
                     ]
    
    remove_tags = [
                     dict(name='div', attrs={'class':'box300'       })
                    ,dict(name='div', style=True                     )
                    ,dict(name='div', attrs={'class':'titcomentario'})
                    ,dict(name='div', attrs={'class':'comentario'   })
                    ,dict(name='div', attrs={'class':'paginador'    })
                  ]
                  
    feeds = [
               (u'Politica', u'http://www.criticadigital.com/herramientas/rss.php?ch=politica'        )
              ,(u'Economia', u'http://www.criticadigital.com/herramientas/rss.php?ch=economia'        )
              ,(u'Deportes', u'http://www.criticadigital.com/herramientas/rss.php?ch=deportes'        )
              ,(u'Espectaculos', u'http://www.criticadigital.com/herramientas/rss.php?ch=espectaculos')
              ,(u'Mundo', u'http://www.criticadigital.com/herramientas/rss.php?ch=mundo'              )
              ,(u'Policiales', u'http://www.criticadigital.com/herramientas/rss.php?ch=policiales'    )
              ,(u'Sociedad', u'http://www.criticadigital.com/herramientas/rss.php?ch=sociedad'        )
              ,(u'Salud', u'http://www.criticadigital.com/herramientas/rss.php?ch=salud'              )
              ,(u'Tecnologia', u'http://www.criticadigital.com/herramientas/rss.php?ch=tecnologia'    )
              ,(u'Santa Fe', u'http://www.criticadigital.com/herramientas/rss.php?ch=santa_fe'        )
            ]

    def get_cover_url(self):
        cover_url = None
        index = 'http://www.criticadigital.com/impresa/'
        soup = self.index_to_soup(index)
        link_item = soup.find('div',attrs={'class':'tapa'})
        if link_item:
           cover_url = index + link_item.img['src']
        return cover_url
