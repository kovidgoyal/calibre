#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class HunTechNet(BasicNewsRecipe):
     title          = u'TechNet'
     oldest_article = 3
     description = u'Az ut\xf3bbi 3 nap TechNet h\xedrei'
     language = 'hu'

     lang = 'hu'
     encoding = 'utf-8'
     __author__ = 'Devilinside'
     max_articles_per_feed = 30
     timefmt = ' [%Y, %b %d, %a]'



     
     remove_tags_before = dict(name='div', attrs={'id':'c-main'})
     remove_tags = [dict(name='div', attrs={'class':'wrp clr'}), 
 {'class' : ['screenrdr','forum','print','startlap','text_small','text_normal','text_big','email']},
                                   ]
     keep_only_tags = [dict(name='div', attrs={'class':'cikk_head box'}),dict(name='div', attrs={'class':'cikk_txt box'})]



     feeds          = [(u'C\xedmlap',
 u'http://www.technet.hu/rss/cimoldal/'), (u'TechTud',
 u'http://www.technet.hu/rss/techtud/'), (u'PDA M\xe1nia',
 u'http://www.technet.hu/rss/pdamania/'), (u'Telefon',
 u'http://www.technet.hu/rss/telefon/'), (u'Sz\xe1m\xedt\xf3g\xe9p',
 u'http://www.technet.hu/rss/notebook/'), (u'GPS',
 u'http://www.technet.hu/rss/gps/')]

