#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Mathieu Godlewski <mathieu at godlewski.fr>'
'''
Mediapart
'''

import re, string
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.web.feeds.news import BasicNewsRecipe

class Mediapart(BasicNewsRecipe):
    title          = 'Mediapart'
    __author__ = 'Mathieu Godlewski <mathieu at godlewski.fr>'
    description = 'Global news in french from online newspapers'
    oldest_article = 7
    language = 'fr'

    max_articles_per_feed = 50
    no_stylesheets = True

    html2lrf_options = ['--base-font-size', '10']

    feeds =  [
        ('Les articles', 'http://www.mediapart.fr/articles/feed'),
    ]

    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE|re.DOTALL), i[1]) for i in
        [
            (r'<div class="print-title">([^>]+)</div>', lambda match : '<h2>'+match.group(1)+'</h2>'),
            (r'<p>Mediapart\.fr</p>', lambda match : ''),
            (r'<p[^>]*>[\s]*</p>', lambda match : ''),
            (r'<p><a href="[^\.]+\.pdf">[^>]*</a></p>', lambda match : ''),
        ]
    ]

    remove_tags    = [ dict(name='div', attrs={'class':'print-source_url'}),
                                  dict(name='div', attrs={'class':'print-links'}),
                                  dict(name='img', attrs={'src':'entete_article.png'}),
    ]


    def print_version(self, url):
        raw = self.browser.open(url).read()
        soup = BeautifulSoup(raw.decode('utf8', 'replace'))
        div = soup.find('div', {'class':'node node-type-article'})
        if div is None:
            return None
        article_id = string.replace(div['id'], 'node-', '')
        if article_id is None:
            return None
        return 'http://www.mediapart.fr/print/'+article_id
