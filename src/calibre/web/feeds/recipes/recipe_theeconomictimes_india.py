#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
economictimes.indiatimes.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class TheEconomicTimes(BasicNewsRecipe):
    title                  = 'The Economic Times India'
    __author__             = 'Darko Miletic'
    description            = 'Financial news from India' 
    publisher              = 'economictimes.indiatimes.com'
    category               = 'news, finances, politics, India'        
    oldest_article         = 2
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    simultaneous_downloads = 1
    encoding               = 'utf-8'
    lang                   = 'en-IN'
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 
    
    feeds          = [(u'All articles', u'http://economictimes.indiatimes.com/rssfeedsdefault.cms')]

    def print_version(self, url):
        rest, sep, art = url.rpartition('/articleshow/')
        return 'http://economictimes.indiatimes.com/articleshow/' + art + '?prtpage=1'

    def get_article_url(self, article):
        rurl = article.get('link',  None)
        if (rurl.find('/quickieslist/') > 0) or (rurl.find('/quickiearticleshow/') > 0):
           return None
        return rurl
        
    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)
        