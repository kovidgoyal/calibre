#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
www.guardian.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Guardian(BasicNewsRecipe):

    title = u'The Guardian'
    __author__ = 'Seabound'
    oldest_article = 7
    max_articles_per_feed = 20

    timefmt = ' [%a, %d %b %Y]'

    remove_tags_before = dict(id='main-article-info')
    remove_tags_after = dict(id='article-wrapper')
    remove_tags_after = dict(id='content')
    no_stylesheets = True
    extra_css = 'h2 {font-size: medium;} \n h1 {text-align: left;}'

    feeds = [

        ('Front Page', 'http://www.guardian.co.uk/rss'),
        ('Business', 'http://www.guardian.co.uk/business/rss'),
        ('Sport', 'http://www.guardian.co.uk/sport/rss'),
        ('Culture', 'http://www.guardian.co.uk/culture/rss'),
        ('Money', 'http://www.guardian.co.uk/money/rss'),
        ('Life & Style', 'http://www.guardian.co.uk/lifeandstyle/rss'),
        ('Travel', 'http://www.guardian.co.uk/travel/rss'),
        ('Environment', 'http://www.guardian.co.uk/environment/rss'),
        ('Comment','http://www.guardian.co.uk/commentisfree/rss'),
        ]
    