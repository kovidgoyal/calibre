#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.usnews.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class LaPrensa(BasicNewsRecipe):
    title                 = 'US & World Report news'
    __author__            = 'Darko Miletic'
    description           = 'News from USA and world'
    publisher             = 'U.S.News & World Report, L.P.'
    category              = 'news, politics, USA'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [
                        dict(name='h1')
                       ,dict(name='div', attrs={'id':['dateline']})
                       ,dict(name='div', attrs={'class':['blogCredit','body']})
                     ]

    feeds = [
              (u'Homepage'        , u'http://www.usnews.com/rss/usnews.rss'          )
             ,(u'Health'          , u'http://www.usnews.com/rss/health/index.rss'    )
             ,(u'Nation & World'  , u'http://www.usnews.com/rss/news/index.rss'      )
             ,(u'Money & Business', u'http://www.usnews.com/rss/business/index.rss'  )
             ,(u'Education'       , u'http://www.usnews.com/rss/education/index.rss' )
             ,(u'Opinion'         , u'http://www.usnews.com/rss/opinion/index.rss'   )
             ,(u'Science'         , u'http://www.usnews.com/rss/science/index.rss'   )
            ]

    def print_version(self, url):
        return url.replace('.html','_print.html')

    def get_article_url(self, article):
        raw = article.get('link',  None)
        artcl, sep, unneeded = raw.rpartition('?')
        return artcl

    def preprocess_html(self, soup):
        del soup.body['onload']
        for item in soup.findAll(style=True):
            del item['style']
        return soup

