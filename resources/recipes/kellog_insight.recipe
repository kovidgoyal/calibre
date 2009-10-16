#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.web.feeds.news import BasicNewsRecipe

class KellogInsight(BasicNewsRecipe):

    title          = 'Kellog Insight'
    __author__     = 'Kovid Goyal'
    description    = 'Articles from the Kellog School of Management'
    no_stylesheets = True
    encoding       = 'utf-8'
    language = 'en'

    oldest_article = 60
    remove_tags_before = {'name':'h1'}
    remove_tags_after = {'class':'col-two-text'}



    feeds = [('Articles',
        'http://insight.kellogg.northwestern.edu/index.php/Kellogg/RSS')]

    def get_article_url(self, article):
        # Get only article not blog links
        link = BasicNewsRecipe.get_article_url(self, article)
        if link and '/article/' in link:
            return link
        self.log('Skipping non-article', link)
        return None
