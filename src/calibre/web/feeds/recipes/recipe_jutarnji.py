#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
jutarnji.hr
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class Jutarnji(BasicNewsRecipe):
    title                 = u'Jutarnji'
    __author__            = u'Darko Miletic'
    description           = u'Hrvatski portal'
    publisher             = 'Jutarnji.hr'
    category              = 'news, politics, Croatia'    
    oldest_article        = 1
    max_articles_per_feed = 100
    simultaneous_downloads = 2
    delay                 = 1
    language              = _('Croatian')
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'cp1250'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 


    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    remove_tags = [ 
                    dict(name=['embed','hr','link','object'])
                   ,dict(name='a', attrs={'class':'a11'})
                  ]
    
    feeds = [
              (u'Naslovnica'      , u'http://www.jutarnji.hr/rss'           )
             ,(u'Sport'           , u'http://www.jutarnji.hr/sport/rss'     )
             ,(u'Jutarnji2'       , u'http://www.jutarnji.hr/j2/rss'        )
             ,(u'Kultura'         , u'http://www.jutarnji.hr/kultura/rss'   )
             ,(u'Spektakli'       , u'http://www.jutarnji.hr/spektakli/rss' )
             ,(u'Dom i nekretnine', u'http://www.jutarnji.hr/nekretnine/rss')
             ,(u'Uhvati ritam'    , u'http://www.jutarnji.hr/kalendar/rss'  )
            ]

    def print_version(self, url):
        main, split, rest = url.partition('.jl')
        rmain, rsplit, rrest = main.rpartition(',')
        return 'http://www.jutarnji.hr/ispis_clanka.jl?artid=' + rrest

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n<meta http-equiv="Content-Language" content="hr-HR"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']        
        for item in soup.findAll(width=True):
            del item['width']        
        return soup
        