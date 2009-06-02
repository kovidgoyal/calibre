#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
globeandmail.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class GlobeAndMail(BasicNewsRecipe):

    title = 'Globe and Mail'
    __author__ = 'Kovid Goyal'
    language = _('English')
    oldest_article = 2.0
    no_stylesheets = True
    description = 'Canada\'s national newspaper'
    remove_tags_before = dict(id="article-top")
    remove_tags = [
            {'id':['util', 'article-tabs', 'comments', 'article-relations',
            'gallery-controls', 'video', 'galleryLoading']},
            ]
    remove_tags_after = dict(id='article-content')

    feeds = [
            ('Latest headlines', 'http://www.theglobeandmail.com/?service=rss'),
            ('Top stories', 'http://www.theglobeandmail.com/?service=rss&feed=topstories'),
            ('National', 'http://www.theglobeandmail.com/news/national/?service=rss'),
            ('Politics', 'http://www.theglobeandmail.com/news/politics/?service=rss'),
            ('World', 'http://www.theglobeandmail.com/news/world/?service=rss'),
            ('Business', 'http://www.theglobeandmail.com/report-on-business/?service=rss'),
            ('Opinions', 'http://www.theglobeandmail.com/news/opinions/?service=rss'),
            ('Columnists', 'http://www.theglobeandmail.com/news/opinions/columnists/?service=rss'),
            ('Globe Investor', 'http://www.theglobeandmail.com/globe-investor/?service=rss'),
            ('Sports', 'http://www.theglobeandmail.com/sports/?service=rss'),
            ('Technology', 'http://www.theglobeandmail.com/news/technology/?service=rss'),
            ('Arts', 'http://www.theglobeandmail.com/news/arts/?service=rss'),
            ('Life', 'http://www.theglobeandmail.com/life/?service=rss'),
            ('Blogs', 'http://www.theglobeandmail.com/blogs/?service=rss'),
            ('Real Estate', 'http://www.theglobeandmail.com/real-estate/?service=rss'),
            ('Auto', 'http://www.theglobeandmail.com/auto/?service=rss'),
            ]
