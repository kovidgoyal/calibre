#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
latimes.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LATimes(BasicNewsRecipe):
    title                 = u'The Los Angeles Times'
    __author__            = u'Darko Miletic'
    description           = u'News from Los Angeles'    
    oldest_article        = 7
    max_articles_per_feed = 100
    language              = _('English')
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    lang                  = 'en-US'

    conversion_options = {
          'comment'          : description
        , 'language'         : lang
    }
    
    keep_only_tags    = [dict(name='div', attrs={'class':'story'   })]
    remove_tags_after = [dict(name='div', attrs={'id':'story-body' })]
    remove_tags       = [dict(name='div', attrs={'class':['thumbnail','articlerail','tools']})]

    feeds          = [(u'News', u'http://feeds.latimes.com/latimes/news')]
    
    def get_article_url(self, article):
        return article.get('feedburner_origlink')
