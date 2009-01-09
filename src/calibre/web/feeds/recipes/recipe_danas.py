#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
danas.rs
'''
import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Danas(BasicNewsRecipe):
    title                 = 'Danas'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne novine sa vestima iz sveta, politike, ekonomije, kulture, sporta, Beograda, Novog Sada i cele Srbije.'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    cover_url = 'http://www.danas.rs/images/basic/danas.gif'
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Serbia'
                        , '--publisher', 'Danas'
                        ]

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [ dict(name='div', attrs={'id':'left'}) ]
    remove_tags = [
                     dict(name='div', attrs={'class':'width_1_4'  })
                    ,dict(name='div', attrs={'class':'metaClanka' })
                    ,dict(name='div', attrs={'id':'comments'      })
                    ,dict(name='div', attrs={'class':'baner'      })
                    ,dict(name='div', attrs={'class':'slikaClanka'})                    
                  ]

    feeds          = [(u'Vesti', u'http://www.danas.rs/rss/rss.asp')]

    def print_version(self, url):
        return url + '&action=print'
