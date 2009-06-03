#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.thebudgetfashionista.com
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class TheBudgetFashionista(BasicNewsRecipe):
    title                  = 'The Budget Fashionista'
    __author__             = 'Darko Miletic'
    description            = 'Saving your money since 2003'
    oldest_article         = 7
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    encoding               = 'utf-8'
    publisher              = 'TBF GROUP, LLC.'
    category               = 'news, fashion, comsetics, women'
    lang                   = 'en-US'
    language               = _('English')

    preprocess_regexps = [(re.compile(r"</head>{0,1}", re.DOTALL|re.IGNORECASE),lambda match: '')]

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'id':'singlepost'})]
    remove_tags_after = dict(name='div', attrs={'id':'postnav'})
    remove_tags = [
                     dict(name=['object','link','script','iframe','form'])
                    ,dict(name='div', attrs={'id':'postnav'})
                  ]

    feeds = [(u'Articles', u'http://www.thebudgetfashionista.com/feeds/atom/')]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    def postprocess_html(self, soup, x):
        body = soup.find('body')
        post = soup.find('div', attrs={'id':'singlepost'})
        if post and body:
          post.extract()
          body.extract()
          soup.html.append(body)
          body.insert(1,post)
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)
