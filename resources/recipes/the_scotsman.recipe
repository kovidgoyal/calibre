#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
thescotsman.scotsman.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheScotsman(BasicNewsRecipe):
    title                 = u'The Scotsman'
    __author__            = 'Darko Miletic'
    description           = 'News from Scotland'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    language = 'en_GB'

    simultaneous_downloads = 1

    keep_only_tags = [dict(name='div', attrs={'id':'viewarticle'})]
    remove_tags = [
                     dict(name='div'  , attrs={'class':'viewarticlepanel' })
                  ]

    feeds          = [
                        (u'Latest National News', u'http://thescotsman.scotsman.com/getFeed.aspx?Format=rss&sectionid=4068'),
                        ('UK', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=7071&format=rss'),
                        ('Scotland', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=7042&format=rss'),
                        ('International', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=7000&format=rss'),
                        ('Politics', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=6990&format=rss'),
                        ('Entertainment', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=7010&format=rss'),
                        ('Features', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=6996&format=rss'),
                        ('Opinion', 'http://thescotsman.scotsman.com/getfeed.aspx?sectionid=7074&format=rss'),
                     ]
