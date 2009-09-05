#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
aljazeera.net
'''
from calibre.web.feeds.news import BasicNewsRecipe

class AlJazeera(BasicNewsRecipe):
    title                  = 'Al Jazeera in English'
    __author__             = 'Darko Miletic'
    description            = 'News from Middle East'
    language = 'en'

    publisher              = 'Al Jazeera'
    category               = 'news, politics, middle east'
    simultaneous_downloads = 1
    delay                  = 4
    oldest_article         = 1
    max_articles_per_feed  = 100
    no_stylesheets         = True
    encoding               = 'iso-8859-1'
    remove_javascript      = True
    use_embedded_content   = False

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_table=True'

    keep_only_tags = [dict(name='div', attrs={'id':'ctl00_divContent'})]

    remove_tags = [
                     dict(name=['object','link'])
                    ,dict(name='td', attrs={'class':['MostActiveDescHeader','MostActiveDescBody']})
                  ]

    feeds = [(u'AL JAZEERA ENGLISH (AJE)', u'http://english.aljazeera.net/Services/Rss/?PostingId=2007731105943979989' )]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(face=True):
            del item['face']
        return soup

