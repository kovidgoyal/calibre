#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
24sata.rs
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class Ser24Sata(BasicNewsRecipe):
    title                 = '24 Sata - Sr'
    __author__            = 'Darko Miletic'
    description           = '24 sata portal vesti iz Srbije'
    publisher             = 'Ringier d.o.o.'
    category              = 'news, politics, entertainment, Serbia'
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    remove_javascript     = True
    language              = _('Serbian')

    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    feeds = [(u'Vesti Dana', u'http://www.24sata.rs/rss.php')]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-RS'
        soup.html['lang']     = 'sr-Latn-RS'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-RS"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        return soup

    def print_version(self, url):
        article, sep, rest = url.partition('#')
        return article.replace('/show.php','/_print.php')

