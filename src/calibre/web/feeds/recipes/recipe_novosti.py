#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
novosti.rs
'''
import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Novosti(BasicNewsRecipe):
    title                 = 'Vecernje Novosti'
    __author__            = 'Darko Miletic'
    description           = 'novosti, vesti, politika, dosije, drustvo, ekonomija, hronika, reportaze, svet, kultura, sport, beograd, regioni, mozaik, feljton, intrvju, pjer, fudbal, kosarka, podvig, arhiva, komentari, kolumne, srbija, republika srpska,Vecernje novosti'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Serbia'
                        , '--publisher', 'Novosti AD'
                        ]

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [ dict(name='div', attrs={'class':'jednaVest'}) ]
    remove_tags_after  = dict(name='div', attrs={'class':'info_bottom'})
    remove_tags = [
                     dict(name='div', attrs={'class':'info'})
                    ,dict(name='div', attrs={'class':'info_bottom'})
                  ]

    feeds          = [ (u'Vesti', u'http://www.novosti.rs/php/vesti/rss.php')]
