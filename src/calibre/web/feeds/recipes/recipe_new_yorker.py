#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
newyorker.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class NewYorker(BasicNewsRecipe):

    title                 = u'The New Yorker'
    __author__            = 'Darko Miletic'
    description           = 'The best of US journalism'
    oldest_article        = 7
    language              = _('English')
    max_articles_per_feed = 100
    no_stylesheets        = False
    use_embedded_content  = False
    extra_css = '''
    .calibre_feed_list {font-size:xx-small}
    .calibre_article_list {font-size:xx-small}
    .calibre_feed_title {font-size:normal}
    .calibre_recipe_title {font-size:normal}
    .calibre_feed_description {font-size:xx-small}
    '''


    keep_only_tags = [
                        dict(name='div'  , attrs={'id':'printbody'   })
                     ]
    remove_tags = [
                     dict(name='div'  , attrs={'class':'utils'       })
                    ,dict(name='div'  , attrs={'id':'bottomFeatures' })
                    ,dict(name='div'  , attrs={'id':'articleBottom'  })
                  ]

    feeds          = [
                        (u'The New Yorker', u'http://feeds.newyorker.com/services/rss/feeds/everything.xml')
                     ]

    def print_version(self, url):
        return url + '?printable=true'
