#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Mathieu Godlewski <mathieu at godlewski.fr>'
'''
Courrier International
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class CourrierInternational(BasicNewsRecipe):
    title          = 'Courrier International'
    __author__ = 'Mathieu Godlewski <mathieu at godlewski.fr>'
    description = 'Global news in french from international newspapers'
    oldest_article = 7
    language = 'fr'

    max_articles_per_feed = 50
    no_stylesheets = True

    html2lrf_options = ['--base-font-size', '10']

    feeds =  [
        # Some articles requiring subscription fails on download.
        ('A la Une', 'http://www.courrierinternational.com/rss/rss_a_la_une.xml'),
    ]

    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE|re.DOTALL), i[1]) for i in
        [
            #Handle Depeches
            (r'.*<td [^>]*>([0-9][0-9]/.*</p>)</td>.*', lambda match : '<html><body><table><tr><td>'+match.group(1)+'</td></tr></table></body></html>'),
            #Handle Articles
            (r'.*<td [^>]*>(Courrier international.*?)							<td width="10"><img src="/img/espaceur.gif"></td>.*', lambda match : '<html><body><table><tr><td>'+match.group(1)+'</body></html>'),
        ]
    ]


    def print_version(self, url):
        return re.sub('/[a-zA-Z]+\.asp','/imprimer.asp' ,url)

