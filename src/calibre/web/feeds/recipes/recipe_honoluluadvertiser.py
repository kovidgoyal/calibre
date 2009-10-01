#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
honoluluadvertiser.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Honoluluadvertiser(BasicNewsRecipe):
    title                 = 'Honolulu Advertiser'
    __author__            = 'Darko Miletic'
    description           = "Latest national and local Hawaii sports news from The Honolulu Advertiser."
    publisher             = 'Honolulu Advertiser'
    category              = 'news, Honolulu, Hawaii'
    oldest_article        = 2
    language              = 'en'
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'

    conversion_options = {
                             'comments'  : description
                            ,'tags'      : category
                            ,'language'  : language
                            ,'publisher' : publisher
                         }

    keep_only_tags = [dict(name='td')]

    remove_tags = [dict(name=['object','link'])]
    remove_attributes = ['style']

    feeds = [
              (u'Breaking news', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS01&MIME=XML' )
             ,(u'Local news', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS02&MIME=XML' )
             ,(u'Sports', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS03&MIME=XML' )
             ,(u'Island life', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS05&MIME=XML' )
             ,(u'Entertainment', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS06&MIME=XML' )
             ,(u'Business', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS04&MIME=XML' )
            ]

    def preprocess_html(self, soup):
        st = soup.find('td')
        if st:
           st.name = 'div'
        return soup

    def print_version(self, url):
        ubody, sep, rest = url.rpartition('?source')
        root, sep2, article_id = ubody.partition('/article/')
        return u'http://www.honoluluadvertiser.com/apps/pbcs.dll/article?AID=/' + article_id + '&template=printart'

