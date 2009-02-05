#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Mathieu Godlewski <mathieu at godlewski.fr>'
'''
lemonde.fr
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe


class LeMonde(BasicNewsRecipe):
    title          = 'LeMonde.fr'
    __author__ = 'Mathieu Godlewski <mathieu at godlewski.fr>'
    description = 'Global news in french'
    oldest_article = 7
    language = _('French')
    max_articles_per_feed = 20
    no_stylesheets = True

    feeds =  [
             ('A la Une', 'http://www.lemonde.fr/rss/une.xml'),
             ('International', 'http://www.lemonde.fr/rss/sequence/0,2-3210,1-0,0.xml'),
             ('Europe', 'http://www.lemonde.fr/rss/sequence/0,2-3214,1-0,0.xml'),
             ('Societe', 'http://www.lemonde.fr/rss/sequence/0,2-3224,1-0,0.xml'),
             ('Economie', 'http://www.lemonde.fr/rss/sequence/0,2-3234,1-0,0.xml'),
             ('Medias', 'http://www.lemonde.fr/rss/sequence/0,2-3236,1-0,0.xml'),
             ('Rendez-vous', 'http://www.lemonde.fr/rss/sequence/0,2-3238,1-0,0.xml'),
             ('Sports', 'http://www.lemonde.fr/rss/sequence/0,2-3242,1-0,0.xml'),
             ('Planete', 'http://www.lemonde.fr/rss/sequence/0,2-3244,1-0,0.xml'),
             ('Culture', 'http://www.lemonde.fr/rss/sequence/0,2-3246,1-0,0.xml'),
             ('Technologies', 'http://www.lemonde.fr/rss/sequence/0,2-651865,1-0,0.xml'),
             ('Cinema', 'http://www.lemonde.fr/rss/sequence/0,2-3476,1-0,0.xml'),
             ('Voyages', 'http://www.lemonde.fr/rss/sequence/0,2-3546,1-0,0.xml'),
             ('Livres', 'http://www.lemonde.fr/rss/sequence/0,2-3260,1-0,0.xml'),
             ('Examens', 'http://www.lemonde.fr/rss/sequence/0,2-3404,1-0,0.xml'),
             ('Opinions', 'http://www.lemonde.fr/rss/sequence/0,2-3232,1-0,0.xml')
             ]

    remove_tags    = [dict(name='img', attrs={'src':'http://medias.lemonde.fr/mmpub/img/lgo/lemondefr_pet.gif'}),
                                    dict(name='div', attrs={'id':'xiti-logo-noscript'}),
                                    dict(name='br', attrs={}),
                                    dict(name='iframe', attrs={}),
    ]

    extra_css      = '.ar-tit {font-size: x-large;} \n .dt {font-size: x-small;}'

    filter_regexps = [r'xiti\.com']

    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
        [
            (r'<p>&nbsp;</p>', lambda match : ''),
            (r'<img src="http://medias\.lemonde\.fr/mmpub/img/let/(.)\.gif"[^>]*><div class=ar-txt>', lambda match : '<div class=ar-txt>'+match.group(1).upper()),
            (r'(<div class=desc><b>.*</b></div>).*</body>', lambda match : match.group(1)),
        ]
    ]

    def print_version(self, url):
        return re.sub('http:.*_([0-9]+)_[0-9]+\.html.*','http://www.lemonde.fr/web/imprimer_element/0,40-0,50-\\1,0.html' ,url)

