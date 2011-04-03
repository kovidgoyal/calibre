#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
liberation.fr
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Liberation(BasicNewsRecipe):
    title                 = u'Liberation'
    __author__            = 'Darko Miletic'
    description           = 'News from France'
    language = 'fr'

    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    
    html2lrf_options = ['--base-font-size', '10']

    keep_only_tags    = [
                           dict(name='h1')
                          ,dict(name='div', attrs={'class':'articleContent'})
                          ,dict(name='div', attrs={'class':'entry'})
                        ]
    remove_tags    = [
                        dict(name='p', attrs={'class':'clear'})
                       ,dict(name='ul', attrs={'class':'floatLeft clear'})
                       ,dict(name='div', attrs={'class':'clear floatRight'})
                       ,dict(name='object')
                     ]
    
    feeds          = [
                         (u'La une', u'http://www.liberation.fr/rss/laune')
                        ,(u'Monde' , u'http://www.liberation.fr/rss/monde')
                        ,(u'Sports', u'http://www.liberation.fr/rss/sports')
                     ]
