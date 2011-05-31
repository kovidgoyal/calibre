#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
tanjug.rs
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Tanjug(BasicNewsRecipe):
    title                 = 'Tanjug'
    __author__            = 'Darko Miletic'
    description           = 'Novinska agencija TANJUG - Dnevne vesti iz Srbije i sveta'
    publisher             = 'Tanjug'
    category              = 'news, politics, Serbia'
    oldest_article        = 2
    max_articles_per_feed = 100
    use_embedded_content  = True
    encoding              = 'utf-8'
    lang                  = 'sr-Latn-RS'
    language = 'sr'

    direction             = 'ltr'
    extra_css             = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    feeds          = [(u'Vesti', u'http://www.tanjug.rs/StaticPages/RssTanjug.aspx')]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang'    ] = self.lang
        soup.html['dir'     ] = self.direction
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        soup.head.insert(0,mlang)
        return self.adeify_images(soup)
