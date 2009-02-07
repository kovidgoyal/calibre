#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
b92.net
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class B92(BasicNewsRecipe):
    title                 = u'B92'
    __author__            = 'Darko Miletic'
    language = _('Serbian')
    description           = 'Dnevne vesti iz Srbije i sveta'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    cover_url = 'http://static.b92.net/images/fp/logo.gif'
    keep_only_tags = [ dict(name='div', attrs={'class':'sama_vest'}) ]
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Serbia'
                        , '--publisher', 'B92'
                        ]
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    feeds          = [
                        (u'Vesti', u'http://www.b92.net/info/rss/vesti.xml')
                       ,(u'Biz'  , u'http://www.b92.net/info/rss/biz.xml'  )
                       ,(u'Zivot', u'http://www.b92.net/info/rss/zivot.xml')
                       ,(u'Sport', u'http://www.b92.net/info/rss/sport.xml')
                     ]

    def print_version(self, url):
        main, sep, article_id = url.partition('nav_id=')
        rmain, rsep, rrest = main.partition('.php?')
        mrmain , rsepp, nnt = rmain.rpartition('/')
        mprmain, rrsep, news_type = mrmain.rpartition('/')
        nurl = 'http://www.b92.net/mobilni/' + news_type + '/index.php?nav_id=' + article_id
        brbiz, biz, bizrest = rmain.partition('/biz/')
        if biz:
            nurl = 'http://www.b92.net/mobilni/biz/index.php?nav_id=' + article_id
        return nurl
