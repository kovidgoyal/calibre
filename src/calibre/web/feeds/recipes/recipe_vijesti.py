#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
vijesti.cg.yu
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe

class Vijesti(BasicNewsRecipe):
    title                 = 'Vijesti'
    __author__            = 'Darko Miletic'
    description           = 'News from Montenegro'
    publisher             = 'Daily Press Vijesti'
    category              = 'news, politics, Montenegro'    
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    remove_javascript     = True
    encoding              = 'cp1250'
    cover_url             = 'http://www.vijesti.cg.yu/img/logo.gif'
    remove_javascript     = True
    use_embedded_content  = False
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "monospace1";src:url(res:///opt/sony/ebook/FONT/tt0419m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: left; font-family: serif1, serif} .article_date{font-family: monospace1, monospace} .article_description{font-family: sans1, sans-serif} .navbar{font-family: monospace1, monospace}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'id':'mainnews'})]

    remove_tags = [
                     dict(name='div', attrs={'align':'right'})
                    ,dict(name=['object','link'])
                  ]

    feeds = [(u'Sve vijesti', u'http://www.vijesti.cg.yu/rss.php' )]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-ME'
        soup.html['lang']     = 'sr-Latn-ME'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-ME"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll('img'):
            if item.has_key('align'):
               del item['align']
               item.insert(0,'<br /><br />')
        return soup

    language              = _('Serbian')