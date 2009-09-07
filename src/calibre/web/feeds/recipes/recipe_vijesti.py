#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
vijesti.me
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Vijesti(BasicNewsRecipe):
    title                 = 'Vijesti'
    __author__            = 'Darko Miletic'
    description           = 'News from Montenegro'
    publisher             = 'Daily Press Vijesti'
    category              = 'news, politics, Montenegro'    
    oldest_article        = 2
    max_articles_per_feed = 150
    no_stylesheets        = True
    encoding              = 'cp1250'
    use_embedded_content  = False
    language = 'sr'

    lang                  ='sr-Latn-Me'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'id':'mainnews'})]

    remove_tags = [dict(name=['object','link','embed'])]

    feeds = [(u'Sve vijesti', u'http://www.vijesti.me/rss.php' )]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)

    def get_article_url(self, article):
        raw = article.get('link',  None)         
        return raw.replace('.cg.yu','.me')
        