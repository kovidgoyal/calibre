"""
publico.py - v1.0

Copyright (c) 2009, David Rodrigues - http://sixhat.net
All rights reserved.
"""

__license__ = 'GPL 3'

from calibre.web.feeds.news import BasicNewsRecipe
import re

class Publico(BasicNewsRecipe):
    title          = u'P\xfablico'
    __author__     = 'David Rodrigues'
    oldest_article = 1
    max_articles_per_feed = 30
    encoding='utf-8'
    no_stylesheets = True
    language = 'pt'

    preprocess_regexps = [(re.compile(u"\uFFFD", re.DOTALL|re.IGNORECASE),  lambda match: ''),]

    feeds          = [
                        (u'Geral', u'http://feeds.feedburner.com/PublicoUltimaHora'),
                        (u'Internacional', u'http://www.publico.clix.pt/rss.ashx?idCanal=11'),
                        (u'Pol\xedtica', u'http://www.publico.clix.pt/rss.ashx?idCanal=12'),
                        (u'Ci\xcencias', u'http://www.publico.clix.pt/rss.ashx?idCanal=13'),
                        (u'Desporto', u'http://desporto.publico.pt/rss.ashx'),
                        (u'Economia', u'http://www.publico.clix.pt/rss.ashx?idCanal=57'),
                        (u'Educa\xe7\xe3o', u'http://www.publico.clix.pt/rss.ashx?idCanal=58'),
                        (u'Local', u'http://www.publico.clix.pt/rss.ashx?idCanal=59'),
                        (u'Media e Tecnologia', u'http://www.publico.clix.pt/rss.ashx?idCanal=61'),
                        (u'Sociedade', u'http://www.publico.clix.pt/rss.ashx?idCanal=62')
                    ]
    remove_tags    = [dict(name='script'), dict(id='linhaTitulosHeader')]
    keep_only_tags = [dict(name='div')]

    def print_version(self,url):
        s=re.findall("id=[0-9]+",url);
        return "http://ww2.publico.clix.pt/print.aspx?"+s[0]
