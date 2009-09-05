#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
newyorker.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class CubaDebate(BasicNewsRecipe):
    title                 = 'CubaDebate'
    __author__            = 'Darko Miletic'
    description           = 'Contra el Terorismo Mediatico'
    oldest_article        = 15
    language = 'es'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    publisher             = 'Cubadebate'
    category              = 'news, politics, Cuba'
    encoding              = 'utf-8'
    extra_css             = ' #BlogTitle{font-size: x-large; font-weight: bold} '
    
    conversion_options = {  
                             'comments'    : description
                            ,'tags'        : category
                            ,'language'    : 'es'
                            ,'publisher'   : publisher
                            ,'pretty_print': True
                         }
                         
    keep_only_tags = [dict(name='div', attrs={'id':'Outline'})]
    remove_tags_after = dict(name='div',attrs={'id':'BlogContent'})
    remove_tags = [dict(name='link')]

    feeds          = [(u'Articulos', u'http://www.cubadebate.cu/feed/')]

    def print_version(self, url):
        return url + 'print/'

    def preprocess_html(self, soup):
        return self.adeify_images(soup)
