#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
jutarnji.hr
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Jutarnji(BasicNewsRecipe):
    title                 = u'Jutarnji'
    __author__            = u'Darko Miletic'
    description           = u'Hrvatski portal'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1250'

    remove_tags = [dict(name='embed')]
    
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
        main = url.partition('.jl')[0]
        rrest = main.rpartition(',')[-1]
        return 'http://www.jutarnji.hr/ispis_clanka.jl?artid=' + rrest

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        return soup
        