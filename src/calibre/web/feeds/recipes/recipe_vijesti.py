#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'

'''
vijesti.cg.yu
'''

import string,re

from calibre.web.feeds.news import BasicNewsRecipe

class Vijesti(BasicNewsRecipe):
    title                 = 'Vijesti'
    __author__            = 'Darko Miletic'
    description           = 'News from Montenegro'    
    oldest_article        = 2
    language              = _('Serbian')
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1250'
    cover_url             = 'http://www.vijesti.cg.yu/img/logo.gif'

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Montenegro'
                        , '--publisher'     , 'Daily Press Vijesti'
                        ]
                        
    keep_only_tags = [dict(name='div', attrs={'id':'mainnews'})]

    feeds = [(u'Sve vijesti', u'http://www.vijesti.cg.yu/rss.php' )]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-ME'
        soup.html['lang']     = 'sr-Latn-ME'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-ME"/>'
        soup.head.insert(0,mtag)
        return soup
