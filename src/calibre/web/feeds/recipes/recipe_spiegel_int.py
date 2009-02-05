#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
spiegel.de
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Spiegel_int(BasicNewsRecipe):
    title                 = u'Spiegel Online International'
    __author__            = 'Darko Miletic'
    description           = "News and POV from Europe's largest newsmagazine"
    oldest_article        = 7
    max_articles_per_feed = 100
    language = _('English')
    no_stylesheets        = True
    use_embedded_content  = False
    cover_url = 'http://www.spiegel.de/static/sys/v8/headlines/spiegelonline.gif'
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, politics, Germany'
                        , '--publisher', 'SPIEGEL ONLINE GmbH'
                        ]

    remove_tags_after = dict(name='div', attrs={'id':'spArticleBody'})

    feeds          = [(u'Spiegel Online', u'http://www.spiegel.de/schlagzeilen/rss/0,5291,676,00.xml')]

    def print_version(self, url):
        main, sep, rest = url.rpartition(',')
        rmain, rsep, rrest = main.rpartition(',')
        return rmain + ',druck-' + rrest + ',' + rest
