#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class H168(BasicNewsRecipe):
     title          = u'168\xf3ra'
     oldest_article = 4
     max_articles_per_feed = 50
     language = 'hu'

     __author__ = 'Ezmegaz'

     feeds          = [(u'Itthon',
 u'http://www.168ora.hu/static/rss/cikkek_itthon.xml'), (u'Gl\xf3busz',
 u'http://www.168ora.hu/static/rss/cikkek_globusz.xml'), (u'Punch',
 u'http://www.168ora.hu/static/rss/cikkek_punch.xml'), (u'Arte',
 u'http://www.168ora.hu/static/rss/cikkek_arte.xml'), (u'Buxa',
 u'http://www.168ora.hu/static/rss/cikkek_buxa.xml'), (u'Sebess\xe9g',
 u'http://www.168ora.hu/static/rss/cikkek_sebesseg.xml'), (u'Tud\xe1s',
 u'http://www.168ora.hu/static/rss/cikkek_tudas.xml'), (u'Sport',
 u'http://www.168ora.hu/static/rss/cikkek_sport.xml'), (u'V\xe9lem\xe9ny',
 u'http://www.168ora.hu/static/rss/cikkek_velemeny.xml'), (u'Dolce Vita',
 u'http://www.168ora.hu/static/rss/cikkek_dolcevita.xml'), (u'R\xe1di\xf3',
 u'http://www.168ora.hu/static/rss/radio.xml')]



