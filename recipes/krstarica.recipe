#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
vesti.krstarica.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class Krstarica(BasicNewsRecipe):
    title                 = 'Krstarica - Vesti'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne vesti iz Srbije i sveta'    
    publisher             = 'Krstarica'
    category              = 'news, politics, Serbia'
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'utf-8'
    language = 'sr'

    extra_css             = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em}"' 
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    feeds          = [
                        (u'Vesti dana'         , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=aktuelno&lang=0'     )
                       ,(u'Srbija'             , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=scg&lang=0'          )
                       ,(u'Svet'               , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=svet&lang=0'         )
                       ,(u'Politika'           , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=politika&lang=0'     )
                       ,(u'Ekonomija'          , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=ekonomija&lang=0'    )
                       ,(u'Drustvo'            , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=drustvo&lang=0'      )
                       ,(u'Kultura'            , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=kultura&lang=0'      )
                       ,(u'Nauka i Tehnologija', u'http://vesti.krstarica.com/index.php?rss=1&rubrika=nauka&lang=0'        )
                       ,(u'Medicina'           , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=medicina&lang=0'     )
                       ,(u'Sport'              , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=sport&lang=0'        )
                       ,(u'Zanimljivosti'      , u'http://vesti.krstarica.com/index.php?rss=1&rubrika=zanimljivosti&lang=0')
                     ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>'
        soup.head.insert(0,mtag)
        titletag = soup.find('h4')
        if titletag:
           realtag = titletag.parent.parent
           realtag.extract()
           for item in soup.findAll(['table','center']):
               item.extract()
           soup.body.insert(1,realtag)            
           realtag.name = 'div'
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(align=True):
            del item['align']
        return soup
