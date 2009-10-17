#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
beta.rs
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Danas(BasicNewsRecipe):
    title                 = 'BETA'
    __author__            = 'Darko Miletic'
    description           = 'Novinska Agencija'
    publisher             = 'Beta'
    category              = 'news, politics, Serbia'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = False
    use_embedded_content  = True
    language = 'sr'

    lang                  = 'sr-Latn-RS'
    direction             = 'ltr'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }


    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    feeds          = [
                        (u'Vesti dana', u'http://www.beta.rs/rssvd.asp')
                       ,(u'Ekonomija' , u'http://www.beta.rs/rssek.asp')
                       ,(u'Sport'     , u'http://www.beta.rs/rsssp.asp')
                     ]

    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)
