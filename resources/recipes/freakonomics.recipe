#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class Freakonomics(BasicNewsRecipe):
    
    title = 'Freakonomics Blog'
    description = 'The Hidden side of everything'
    __author__ = 'Kovid Goyal'
    language = 'en'

    
    feeds = [('Blog', 'http://freakonomics.blogs.nytimes.com/feed/atom/')]
    
    def get_article_url(self, article):
        return article.get('feedburner_origlink', None)
        
    def print_version(self, url):
        return url + '?pagemode=print'