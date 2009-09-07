#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
politika.rs
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Politika(BasicNewsRecipe):
    title                 = 'Politika Online'
    __author__            = 'Darko Miletic'
    description           = 'Najstariji dnevni list na Balkanu'
    publisher             = 'Politika novine i Magazini d.o.o'
    category              = 'news, politics, Serbia'            
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'utf8'
    language = 'sr'

    lang                 = 'sr-Latn-RS'
    direction            = 'ltr'    
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }
    

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'class':'content_center_border'})]

    remove_tags = [ 
                    dict(name='div', attrs={'class':['send_print','txt-komentar']})
                   ,dict(name=['object','link','a'])
                   ,dict(name='h1', attrs={'class':'box_header-tags'})                   
                  ]
    

    feeds          = [  
                         (u'Politika'             , u'http://www.politika.rs/rubrike/Politika/index.1.lt.xml'             )
                        ,(u'Svet'                 , u'http://www.politika.rs/rubrike/Svet/index.1.lt.xml'                 )
                        ,(u'Redakcijski komentari', u'http://www.politika.rs/rubrike/redakcijski-komentari/index.1.lt.xml')
                        ,(u'Pogledi'              , u'http://www.politika.rs/pogledi/index.lt.xml'                        )
                        ,(u'Pogledi sa strane'    , u'http://www.politika.rs/rubrike/Pogledi-sa-strane/index.1.lt.xml'    )
                        ,(u'Tema dana'            , u'http://www.politika.rs/rubrike/tema-dana/index.1.lt.xml'            )
                        ,(u'Kultura'              , u'http://www.politika.rs/rubrike/Kultura/index.1.lt.xml'              )
                        ,(u'Zivot i stil'         , u'http://www.politika.rs/rubrike/zivot-i-stil/index.1.lt.xml'         )                        
                     ]

    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction      
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        soup.head.insert(0,mlang)
        for item in soup.findAll(style=True):
            del item['style']
        ftag = soup.find('div',attrs={'class':'content_center_border'})
        if ftag.has_key('align'):
           del ftag['align']
        return self.adeify_images(soup)
