#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.web.feeds.news import BasicNewsRecipe

class HunMilNews(BasicNewsRecipe):
    title          = u'Honvedelem.hu'
    oldest_article = 3
    description = u'Katonah\xedrek'
    language = 'hu'

    lang = 'hu'
    encoding = 'windows-1250'
    category = 'news, military'

    no_stylesheets         = True


    __author__ = 'Devilinside'
    max_articles_per_feed = 16
    no_stylesheets = True



    keep_only_tags = [dict(name='div', attrs={'class':'cikkoldal_cikk_cim'}),
 dict(name='div', attrs={'class':'cikkoldal_cikk_alcim'}),
 dict(name='div', attrs={'class':'cikkoldal_datum'}),
 dict(name='div', attrs={'class':'cikkoldal_lead'}),
 dict(name='div', attrs={'class':'cikkoldal_szoveg'}),
 dict(name='img', attrs={'class':'ajanlo_kep_keretes'}),
        ]



    feeds          = [(u'Misszi\xf3k', u'http://www.honvedelem.hu/rss_b?c=22'),
 (u'Aktu\xe1lis hazai h\xedrek', u'http://www.honvedelem.hu/rss_b?c=3'),
 (u'K\xfclf\xf6ldi h\xedrek', u'http://www.honvedelem.hu/rss_b?c=4'),
 (u'A h\xf3nap t\xe9m\xe1ja', u'http://www.honvedelem.hu/rss_b?c=6'),
 (u'Riport', u'http://www.honvedelem.hu/rss_b?c=5'),
 (u'Portr\xe9k', u'http://www.honvedelem.hu/rss_b?c=7'),
 (u'Haditechnika', u'http://www.honvedelem.hu/rss_b?c=8'),
 (u'Programok, esem\xe9nyek', u'http://www.honvedelem.hu/rss_b?c=12')
        ]

