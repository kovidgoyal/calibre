#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.thebudgetfashionista.com
'''

from calibre.web.feeds.recipes import BasicNewsRecipe

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
    language = 'en'


    conversion_options = {
          'comment'          : description
        , 'tags'             : category
        , 'publisher'        : publisher
        , 'language'         : lang
    }

    keep_only_tags = [dict(name='div', attrs={'class':'columnLeft'})]
    remove_tags_after = dict(name='div', attrs={'class':'postDetails'})
    remove_tags = [dict(name=['object','link','script','iframe','form','login-button'])]

    feeds = [(u'Articles', u'http://www.thebudgetfashionista.com/feeds/atom/')]

    def preprocess_html(self, soup):
        for it in soup.findAll('img'):
            if it.parent.name == 'a':
               it.parent.name = 'div'
        return soup;

