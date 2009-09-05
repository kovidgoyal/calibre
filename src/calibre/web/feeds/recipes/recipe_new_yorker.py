#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
newyorker.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class NewYorker(BasicNewsRecipe):
    title                 = 'The New Yorker'
    __author__            = 'Darko Miletic'
    description           = 'The best of US journalism'
    oldest_article        = 15
    language = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    publisher             = 'Conde Nast Publications'
    category              = 'news, politics, USA'
    encoding              = 'cp1252'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'id':'printbody'})]
    remove_tags_after = dict(name='div',attrs={'id':'articlebody'})
    remove_tags = [
                     dict(name='div', attrs={'class':['utils','articleRailLinks','icons'] })
                    ,dict(name='link')
                  ]

    feeds          = [(u'The New Yorker', u'http://feeds.newyorker.com/services/rss/feeds/everything.xml')]

    def print_version(self, url):
        return url + '?printable=true'

    def get_article_url(self, article):
        return article.get('guid',  None)

    def postprocess_html(self, soup, x):
        body = soup.find('body')
        if body:
            html = soup.find('html')
            if html:
                body.extract()
                html.insert(2, body)
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(1,mcharset)
        return soup
