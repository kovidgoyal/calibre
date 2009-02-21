#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
e-novine.com
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class E_novine(BasicNewsRecipe):
    title                 = 'E-Novine'
    __author__            = 'Darko Miletic'
    description           = 'News from Serbia'
    publisher             = 'E-novine'
    category              = 'news, politics, Balcans'
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'cp1250'
    cover_url             = 'http://www.e-novine.com/slike/slike_3/r1/g2008/m03/y3165525326702598.jpg'
    remove_javascript     = True
    use_embedded_content  = False
    language              = _('Serbian')
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'id':['css_47_0_2844H']})]

    remove_tags = [dict(name=['object','link','embed','iframe'])]

    feeds = [(u'Sve vesti', u'http://www.e-novine.com/rss/e-novine.xml' )]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-ME'
        soup.html['lang']     = 'sr-Latn-ME'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-ME"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        ftag = soup.find('div', attrs={'id':'css_47_0_2844H'})
        if ftag:
           it = ftag.div
           it.extract()
           ftag.div.extract()
           ftag.insert(0,it)
        return soup
