#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
timesonline.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TimesOnline(BasicNewsRecipe):
    title                 = u'The Times Online'
    __author__            = 'Darko Miletic'
    description           = 'UK news'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    simultaneous_downloads = 1

    remove_tags_after  = dict(name='div', attrs={'class':'bg-666'})
    remove_tags = [
                     dict(name='div'  , attrs={'class':'hide-from-print padding-bottom-7' })
                  ]

    feeds          = [
                        (u'Top stories from Times Online', u'http://www.timesonline.co.uk/tol/feeds/rss/topstories.xml'     ),
                        ('Latest Business News', 'http://www.timesonline.co.uk/tol/feeds/rss/business.xml'),
                        ('Economics', 'http://www.timesonline.co.uk/tol/feeds/rss/economics.xml'),
                        ('World News', 'http://www.timesonline.co.uk/tol/feeds/rss/worldnews.xml'),
                        ('UK News', 'http://www.timesonline.co.uk/tol/feeds/rss/uknews.xml'),
                        ('Travel News', 'http://www.timesonline.co.uk/tol/feeds/rss/travel.xml'),
                        ('Sports News', 'http://www.timesonline.co.uk/tol/feeds/rss/sport.xml'),
                        ('Film News', 'http://www.timesonline.co.uk/tol/feeds/rss/film.xml'),
                        ('Tech news', 'http://www.timesonline.co.uk/tol/feeds/rss/tech.xml'),
                     ]

    def print_version(self, url):
        main = url.partition('#')[0]
        return main + '?print=yes'