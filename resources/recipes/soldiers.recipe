#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.army.mil/soldiers/
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Soldiers(BasicNewsRecipe):
    title                  = 'Soldiers'
    __author__             = 'Darko Miletic'
    description            = 'The Official U.S. Army Magazine'
    oldest_article         = 30
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    remove_javascript      = True 
    simultaneous_downloads = 1
    delay                  = 4
    max_connections        = 1    
    encoding               = 'utf-8'
    publisher              = 'U.S. Army'
    category               = 'news, politics, war, weapons'    
    language = 'en'

    INDEX                  = 'http://www.army.mil/soldiers/'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    keep_only_tags = [dict(name='div', attrs={'id':'rightCol'})]
                     
    remove_tags = [
                     dict(name='div', attrs={'id':['addThis','comment','articleFooter']})
                    ,dict(name=['object','link'])
                  ]
                            
    feeds = [(u'Frontpage', u'http://www.army.mil/rss/feeds/soldiersfrontpage.xml' )]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        cover_item = soup.find('img',attrs={'alt':'Current Magazine Cover'})
        if cover_item:
           cover_url = cover_item['src']
        return cover_url
