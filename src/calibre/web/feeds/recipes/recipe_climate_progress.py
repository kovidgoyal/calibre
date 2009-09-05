#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
climateprogress.org
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class ClimateProgress(BasicNewsRecipe):
    title                 = 'Climate Progress'
    __author__            = 'Darko Miletic'
    description           = "An insider's view of climate science, politics and solutions"
    publisher             = 'Climate Progress'
    category              = 'news, ecology, climate, blog'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = True
    encoding              = 'utf-8'
    language = 'en'

    lang                  = 'en-US'
    direction             = 'ltr'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    feeds = [(u'Posts', u'http://feeds.feedburner.com/climateprogress/lCrX')]
    
    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)
    
