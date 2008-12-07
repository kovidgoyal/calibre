#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
nspm.rs
'''

import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Nspm(BasicNewsRecipe):
    title                 = u'Nova srpska politicka misao'
    __author__            = 'Darko Miletic'
    description           = 'Casopis za politicku teoriju i drustvena istrazivanja'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    INDEX                 = 'http://www.nspm.rs/?alphabet=l'
    timefmt               = ' [%A, %d %B, %Y]' 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.INDEX)
        return br

    feeds = [ (u'Nova srpska politicka misao', u'http://www.nspm.rs/feed/rss.html')]

    def print_version(self, url):
        return url.replace('.html','/stampa.html')
