#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
rbc.org
'''

from calibre.web.feeds.news import BasicNewsRecipe

class OurDailyBread(BasicNewsRecipe):
    title                 = 'Our Daily Bread'
    __author__            = 'Darko Miletic'
    description           = 'Religion'
    oldest_article        = 15
    language = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    category              = 'religion'
    encoding              = 'utf-8'
    extra_css             = ' #devoTitle{font-size: x-large; font-weight: bold} '
    
    conversion_options = {  
                             'comments'    : description
                            ,'tags'        : category
                            ,'language'    : 'en'
                         }
                         
    keep_only_tags = [dict(name='div', attrs={'class':['altbg','text']})]

    feeds          = [(u'Our Daily Bread', u'http://www.rbc.org/rss.ashx?id=50398')]

    def preprocess_html(self, soup):
        return self.adeify_images(soup)
