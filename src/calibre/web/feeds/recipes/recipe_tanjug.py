#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
tanjug.rs
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class Tanjug(BasicNewsRecipe):
    title                 = 'Tanjug'
    __author__            = 'Darko Miletic'
    description           = 'Novinska agencija TANJUG - Dnevne vesti iz Srbije i sveta'
    publisher             = 'Tanjug'
    category              = 'news, politics, Serbia'
    oldest_article        = 1
    max_articles_per_feed = 100
    use_embedded_content  = True
    encoding              = 'utf-8'
    lang                  = 'sr-Latn-RS'
    language              = _('Serbian')
    extra_css             = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em}"' 
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    feeds          = [(u'Vesti', u'http://www.tanjug.rs/StaticPages/RssTanjug.aspx')]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang'    ] = self.lang
        soup.html['dir'     ] = "ltr"
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>'
        soup.head.insert(0,mtag)
        return soup
