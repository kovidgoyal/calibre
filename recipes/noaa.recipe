#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
noaa.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class NOAA(BasicNewsRecipe):
    title                  = 'NOAA Online'
    __author__             = 'Darko Miletic'
    description            = 'NOAA'
    publisher              = 'NOAA'
    category               = 'news, science, US, ocean'
    oldest_article         = 15
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    simultaneous_downloads = 1
    encoding               = 'utf-8'
    lang                   = 'en-US'
    language = 'en'



    remove_tags        = [dict(name=['embed','object'])]
    keep_only_tags     = [dict(name='div', attrs={'id':'contentArea'})]

    feeds          = [(u'NOAA articles', u'http://www.rss.noaa.gov/noaarss.xml')]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)

