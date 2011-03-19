#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
beta.rs
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Danas(BasicNewsRecipe):
    title                 = 'BETA - English'
    __author__            = 'Darko Miletic'
    description           = 'Serbian news agency'
    publisher             = 'Beta'
    category              = 'news, politics, Serbia'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = False
    use_embedded_content  = True
    language = 'en'

    lang                  = 'en'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }


    feeds          = [(u'News', u'http://www.beta.rs/rssen.asp')]

    def preprocess_html(self, soup):
        return self.adeify_images(soup)
