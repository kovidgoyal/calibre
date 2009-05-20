#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class Slashdot(BasicNewsRecipe):
             title          = u'Slashdot.org'
             oldest_article = 7
             max_articles_per_feed = 100
             language = _('English')
             __author__ = 'floweros'
             no_stylesheets = True
             keep_only_tags = [dict(name='div',attrs={'id':'article'})]
             remove_tags    = [
                 dict(name='div',attrs={'id':'userlogin-title'}),
                 dict(name='div',attrs={'id':'userlogin-content'}),
                 dict(name='div',attrs={'id':'commentwrap'}),
                 dict(name='span',attrs={'id':'more_comments_num_a'}),
                 ]

             feeds          = [
                 (u'Slashdot',
 u'http://rss.slashdot.org/Slashdot/slashdot?m=5072'),
                 (u'/. IT',
 u'http://rss.slashdot.org/Slashdot/slashdotIT'),
                 (u'/. Hardware',
 u'http://rss.slashdot.org/Slashdot/slashdotHardware'),
                 (u'/. Linux',
 u'http://rss.slashdot.org/Slashdot/slashdotLinux'),
                 (u'/. Your Rights Online',
 u'http://rss.slashdot.org/Slashdot/slashdotYourRightsOnline')
                 ]


