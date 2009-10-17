#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class AdvancedUserRecipe1249039563(BasicNewsRecipe):
    title          = u'De Volkskrant'
    __author__     = 'acidzebra'
    oldest_article = 7
    max_articles_per_feed = 100
    no_stylesheets = True
    language = 'nl'

    keep_only_tags = [dict(name='div', attrs={'id':'leftColumnArticle'}) ]
    remove_tags    = [
        dict(name='div',attrs={'class':'article_tools'}),
        dict(name='div',attrs={'id':'article_tools'}),
        dict(name='div',attrs={'class':'articletools'}),
        dict(name='div',attrs={'id':'articletools'}),
        dict(name='div',attrs={'id':'myOverlay'}),
        dict(name='div',attrs={'id':'trackback'}),
        dict(name='div',attrs={'id':'googleBanner'}),
        dict(name='div',attrs={'id':'article_headlines'}),
        ]
    extra_css      = '''
                        body{font-family:Arial,Helvetica,sans-serif; font-size:small;}
                        h1{font-size:large;}
                     '''

    feeds          = [(u'Laatste Nieuws', u'http://volkskrant.nl/rss/laatstenieuws.rss'), (u'Binnenlands nieuws', u'http://volkskrant.nl/rss/nederland.rss'), (u'Buitenlands nieuws', u'http://volkskrant.nl/rss/internationaal.rss'), (u'Economisch nieuws', u'http://volkskrant.nl/rss/economie.rss'), (u'Sportnieuws', u'http://volkskrant.nl/rss/sport.rss'), (u'Kunstnieuws', u'http://volkskrant.nl/rss/kunst.rss'), (u'Wetenschapsnieuws', u'http://feeds.feedburner.com/DeVolkskrantWetenschap'), (u'Technologienieuws', u'http://feeds.feedburner.com/vkmedia')]
