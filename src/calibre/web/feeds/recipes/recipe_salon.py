#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe


class Salon_com(BasicNewsRecipe):
    title = 'Salon.com'
    __author__ = 'cix3'
    description = 'Salon.com - Breaking news, opinion, politics, entertainment, sports and culture.'
    timefmt = ' [%b %d, %Y]'
    language = 'en'

    oldest_article = 7
    max_articles_per_feed = 100

    remove_tags = [dict(name='div', attrs={'class':['ad_content', 'clearfix']}), dict(name='hr'), dict(name='img')]

    remove_tags_before = dict(name='h2')

    feeds = [
        ('News & Politics', 'http://feeds.salon.com/salon/news'),
        ('War Room', 'http://feeds.salon.com/salon/war_room'),
        ('Arts & Entertainment', 'http://feeds.salon.com/salon/ent'),
        ('I Like to Watch', 'http://feeds.salon.com/salon/iltw'),
        ('Beyond Multiplex', 'http://feeds.salon.com/salon/btm'),
        ('Book Reviews', 'http://feeds.salon.com/salon/books'),
        ('All Life', 'http://feeds.salon.com/salon/mwt'),
        ('All Opinion', 'http://feeds.salon.com/salon/opinion'),
        ('Glenn Greenwald', 'http://feeds.salon.com/salon/greenwald'),
        ('Garrison Keillor', 'http://dir.salon.com/topics/garrison_keillor/index.rss'),
        ('Joan Walsh', 'http://www.salon.com/rss/walsh.rss'),
        ('All Sports', 'http://feeds.salon.com/salon/sports'),
        ('Tech & Business', 'http://feeds.salon.com/salon/tech'),
        ('How World Works', 'http://feeds.salon.com/salon/htww')
            ]

    def print_version(self, url):
        return url.replace('/index.html', '/print.html')


