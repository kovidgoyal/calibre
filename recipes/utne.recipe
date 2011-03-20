#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
utne.com
'''

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.web.feeds.news import BasicNewsRecipe

class Utne(BasicNewsRecipe):
    title                 = u'Utne reader'
    __author__            = 'Darko Miletic'
    description           = 'News'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    language = 'en'

    
    cover_url = 'http://www.utne.com/images/template/logo.gif'
    
    remove_tags = [
                     dict(name='a' , attrs={'id':'ctl00_blankmaster_lnkBanner' })
                    ,dict(name='object')
                  ]

    feeds          = [
                        (u'Politics'     , u'http://www.utne.com/rss/Politics.xml')
                       ,(u'Environment'  , u'http://www.utne.com/rss/Environment.xml')
                       ,(u'Media'        , u'http://www.utne.com/rss/Media.xml')
                       ,(u'Great writing', u'http://www.utne.com/rss/Great-Writing.xml')
                       ,(u'Science & Technology', u'http://www.utne.com/rss/Science-Technology.xml')
                       ,(u'Arts', u'http://www.utne.com/rss/Arts.xml')
                     ]
        
    def print_version(self, url):
        raw = self.browser.open(url).read()
        soup = BeautifulSoup(raw.decode('utf8', 'replace'))
        print_link = soup.find('a', {'id':'ctl00_defaultmaster_Blog_tools1_lnkPrint'})
        if print_link is None:
            return url
        return print_link['href']

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        del(soup.body['onload'])
        return soup
