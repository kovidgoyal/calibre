#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
exiledonline.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Exiled(BasicNewsRecipe):
    title                 = 'Exiled Online'
    __author__            = 'Darko Miletic'
    description           = "Mankind's only alternative since 1997 - Formerly known as The eXile"
    publisher             = 'Exiled Online'
    category              = 'news, politics, international'
    oldest_article        = 15
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf8'
    remove_javascript     = True
    language = 'en'

    cover_url             = 'http://exiledonline.com/wp-content/themes/exiledonline_theme/images/header-sm.gif'

    html2lrf_options = [
                          '--comment'       , description
                        , '--base-font-size', '10'
                        , '--category'      , category
                        , '--publisher'     , publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'id':'main'})]

    remove_tags = [
                     dict(name=['object','link'])
                    ,dict(name='div', attrs={'class':'info'})
                    ,dict(name='div', attrs={'id':['comments','navig']})
                  ]


    feeds = [(u'Articles', u'http://exiledonline.com/feed/')]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        mtag = '\n<meta http-equiv="Content-Language" content="en"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        soup.head.insert(0,mtag)
        return soup

    def get_article_url(self, article):
        raw = article.get('link',  None)
        final = raw + 'all/1/'
        return final

