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
        ('All News & Politics', 'http://feeds.salon.com/salon/news'),
        ('War Room', 'http://feeds.salon.com/salon/war_room'),
        ('All Arts & Entertainment', 'http://feeds.salon.com/salon/ent'),
        ('I Like to Watch', 'http://feeds.salon.com/salon/iltw'),
        ('Book Reviews', 'http://feeds.salon.com/salon/books'),
        ('All Life stories', 'http://feeds.salon.com/salon/mwt'),
        ('Broadsheet', 'http://feeds.salon.com/salon/broadsheet'),
        ('All Opinion', 'http://feeds.salon.com/salon/opinion'),
        ('All Sports', 'http://feeds.salon.com/salon/sports'),
        ('All Tech & Business', 'http://feeds.salon.com/salon/tech'),
        ('Ask the Pilot', 'http://feeds.salon.com/salon/ask_the_pilot'),
        ('How the World Works', 'http://feeds.salon.com/salon/htww')
            ]

    def print_version(self, url):
        return url.replace('/index.html', '/print.html')
