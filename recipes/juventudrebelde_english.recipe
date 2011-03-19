#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
juventudrebelde.co.cu
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Juventudrebelde_english(BasicNewsRecipe):
    title                 = 'Juventud Rebelde in english'
    __author__            = 'Darko Miletic'
    description           = 'The newspaper of Cuban Youth'
    publisher             = 'Juventud Rebelde'
    category              = 'news, politics, Cuba'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'iso-8859-1'
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'class':'read'})]

    feeds = [(u'All news', u'http://www.juventudrebelde.cip.cu/rss/all/' )]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CU"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = 'en'
