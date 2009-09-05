#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
www.esquire.com
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Esquire(BasicNewsRecipe):
    title                 = 'Esquire'
    __author__            = 'Darko Miletic'
    description           = 'Esquire: Man at His Best'
    publisher             = 'Hearst Communications, Inc.'
    category              = 'magazine, men, women we love, style, the guide, sex, screen'
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'cp1250'
    use_embedded_content  = False
    language = 'en'

    lang                  = 'en-US'
    cover_url             = strftime('http://www.esquire.com/cm/esquire/cover-images/%Y_') + strftime('%m').strip('0') + '.jpg'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }

    keep_only_tags = [dict(name='div', attrs={'id':'content'})]

    remove_tags = [dict(name=['object','link','embed','iframe'])]

    feeds = [
               (u'Style'    , u'http://www.esquire.com/style/rss/'    )
              ,(u'Women'    , u'http://www.esquire.com/women/rss/'    )
              ,(u'Features' , u'http://www.esquire.com/features/rss/' )
              ,(u'Fiction'  , u'http://www.esquire.com/fiction/rss/'  )
              ,(u'Frontpage', u'http://www.esquire.com/rss/'          )
            ]


    def print_version(self, url):
        rest = url.rpartition('?')[0]
        article = rest.rpartition('/')[2]
        return 'http://www.esquire.com/print-this/' + article

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        soup.head.insert(0,mlang)
        for item in soup.findAll(style=True):
            del item['style']
        return soup
