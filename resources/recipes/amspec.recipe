#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
spectator.org
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheAmericanSpectator(BasicNewsRecipe):
    title                 = 'The American Spectator'
    __author__            = 'Darko Miletic'
    language = 'en'

    description           = 'News from USA'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    INDEX                 = 'http://spectator.org'
      
    html2lrf_options = [
                             '--comment'       , description
                           , '--category'      , 'news, politics, USA'
                           , '--publisher'     , title
                         ]

    keep_only_tags   = [
                             dict(name='div', attrs={'class':'post inner'})
                            ,dict(name='div', attrs={'class':'author-bio'})
                         ]

    remove_tags     = [
                             dict(name='object')
                            ,dict(name='div', attrs={'class':'col3'         })
                            ,dict(name='div', attrs={'class':'post-options' })
                            ,dict(name='p'  , attrs={'class':'letter-editor'})
                            ,dict(name='div', attrs={'class':'social'       })
                        ]
                         
    feeds = [ (u'Articles', u'http://feedproxy.google.com/amspecarticles')]

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        link_item = soup.find('a',attrs={'class':'cover'})
        if link_item:
            soup2 = self.index_to_soup(link_item['href'])
            link_item2 = soup2.find('div',attrs={'class':'post inner issues'})
            cover_url = self.INDEX + link_item2.img['src']
        return cover_url
          
    def print_version(self, url):
        return url + '/print'
