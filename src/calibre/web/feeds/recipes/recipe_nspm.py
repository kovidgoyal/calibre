#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
nspm.rs
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe

class Nspm(BasicNewsRecipe):
    title                 = u'Nova srpska politicka misao'
    __author__            = 'Darko Miletic'
    description           = 'Casopis za politicku teoriju i drustvena istrazivanja'    
    publisher             = 'NSPM'
    category              = 'news, politics, Serbia'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    INDEX                 = 'http://www.nspm.rs/?alphabet=l'
    encoding              = 'utf8'
    remove_javascript     = True
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "monospace1";src:url(res:///opt/sony/ebook/FONT/tt0419m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: left; font-family: serif1, serif} .article_date{font-family: monospace1, monospace} .article_description{font-family: sans1, sans-serif} .navbar{font-family: monospace1, monospace}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    remove_tags        = [dict(name='a')]
    
    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.INDEX)
        return br

    feeds = [(u'Nova srpska politicka misao', u'http://www.nspm.rs/feed/rss.html')]

    def print_version(self, url):
        return url.replace('.html','/stampa.html')

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-RS'
        soup.html['lang']     = 'sr-Latn-RS'
        ftag = soup.find('meta',attrs={'http-equiv':'Content-Language'})
        if ftag:
           ftag['content'] = 'sr-Latn-RS'
        for item in soup.findAll(style=True):
            del item['style']        
        return soup

    language = _('Serbian')