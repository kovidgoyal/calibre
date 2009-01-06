#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
jutarnji.hr
'''

import string, re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class Jutarnji(BasicNewsRecipe):
    title                 = 'Jutarnji'
    __author__            = 'Darko Miletic'
    description           = 'Online izdanje Jutarnjeg lista'
    oldest_article        = 2
    max_articles_per_feed = 100
    simultaneous_downloads = 1
    delay = 1    
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1250'
    cover_url = 'http://www.jutarnji.hr/EPHResources/Images/2008/06/05/jhrlogo.png'
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Croatia'
                        , '--publisher', 'Europapress holding d.o.o.'
                        ]    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    remove_tags = [ 
                    dict(name='embed')
                   ,dict(name='a', attrs={'class':'a11'})
                   ,dict(name='hr')
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
        return u'http://www.jutarnji.hr/ispis_clanka.jl?artid=' + rrest

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        soup.prettify()
        return soup
        