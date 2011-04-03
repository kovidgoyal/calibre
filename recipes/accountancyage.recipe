#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.accountancyage.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class AccountancyAge(BasicNewsRecipe):
    title                  = 'Accountancy Age'
    __author__             = 'Darko Miletic'
    description            = 'business news'
    publisher              = 'accountancyage.com'
    category               = 'news, politics, finances'
    oldest_article         = 2
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    simultaneous_downloads = 1
    encoding               = 'utf-8'
    lang                   = 'en'
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags      = [dict(name='div', attrs={'class':'bodycol'})]
    remove_tags         = [dict(name=['embed','object'])]
    remove_tags_after   = dict(name='div', attrs={'id':'permalink'})
    remove_tags_before  = dict(name='div', attrs={'class':'gap6'})

    feeds          = [(u'All News', u'http://feeds.accountancyage.com/rss/latest/accountancyage/all')]

    def print_version(self, url):
        rest, sep, miss = url.rpartition('/')
        rr, ssep, artid = rest.rpartition('/')
        return u'http://www.accountancyage.com/articles/print/' + artid

    def get_article_url(self, article):
        return article.get('guid',  None)

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)

