#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
blic.rs
'''
import string,re
from calibre.web.feeds.news import BasicNewsRecipe

class Blic(BasicNewsRecipe):
    title                 = u'Blic'
    __author__            = 'Darko Miletic'
    description           = 'Blic.rs online verzija najtiraznije novine u Srbiji donosi najnovije vesti iz Srbije i sveta, komentare, politicke analize, poslovne i ekonomske vesti, vesti iz regiona, intervjue, informacije iz kulture, reportaze, pokriva sve sportske dogadjaje, detaljan tv program, nagradne igre, zabavu, fenomenalni Blic strip, dnevni horoskop, arhivu svih dogadjaja'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    cover_url = 'http://www.blic.rs/resources/images/header_back_tile.png'
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, Serbia'
                        , '--publisher', 'Blic'
                        ]

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [ dict(name='div', attrs={'class':'single_news'}) ]

    feeds          = [ (u'Vesti', u'http://www.blic.rs/rssall.php')]

    def print_version(self, url):
        start_url, question, rest_url = url.partition('?')
        return u'http://www.blic.rs/_print.php?' + rest_url
