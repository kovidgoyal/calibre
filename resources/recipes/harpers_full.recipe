#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
harpers.org - paid subscription/ printed issue articles
This recipe only get's article's published in text format
images and pdf's are ignored
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Harpers_full(BasicNewsRecipe):
    title                 = u"Harper's Magazine - articles from printed edition"
    __author__            = u'Darko Miletic'
    description           = u"Harper's Magazine: Founded June 1850."
    publisher             = "Harpers's"
    category              = 'news, politics, USA'
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    delay                  = 1
    language = 'en'

    needs_subscription = True
    INDEX = strftime('http://www.harpers.org/archive/%Y/%m')
    LOGIN = 'http://www.harpers.org'
    cover_url = strftime('http://www.harpers.org/media/pages/%Y/%m/gif/0001.gif')

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"'

    keep_only_tags = [ dict(name='div', attrs={'id':'cached'}) ]
    remove_tags = [
                     dict(name='table', attrs={'class':['rcnt','rcnt topline']})
                    ,dict(name='link')
                  ]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open(self.LOGIN)
            br.select_form(nr=1)
            br['handle'  ] = self.username
            br['password'] = self.password
            br.submit()
        return br

    def parse_index(self):
        articles = []
        print 'Processing ' + self.INDEX
        soup = self.index_to_soup(self.INDEX)
        for item in soup.findAll('div', attrs={'class':'title'}):
            text_link = item.parent.find('img',attrs={'alt':'Text'})
            if text_link:
                url   = self.LOGIN + item.a['href']
                title = item.a.contents[0]
                date  = strftime(' %B %Y')
                articles.append({
                                  'title'      :title
                                 ,'date'       :date
                                 ,'url'        :url
                                 ,'description':''
                                })
        return [(soup.head.title.string, articles)]

    def preprocess_html(self, soup):
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(1,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(xmlns=True):
            del item['xmlns']
        return soup
