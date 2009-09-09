#!/usr/bin/env  python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Gerhard Aigner <gerhard.aigner at gmail.com>'

''' http://www.derstandard.at - Austrian Newspaper '''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class DerStandardRecipe(BasicNewsRecipe):
    title = u'derStandard'
    __author__ = 'Gerhard Aigner'
    description = u'Nachrichten aus Österreich' 
    publisher ='derStandard.at'
    category = 'news, politics, nachrichten, Austria'
    use_embedded_content = False
    remove_empty_feeds = True
    lang = 'de-AT'
    no_stylesheets = True
    encoding = 'utf-8'
    language = 'de'

    recursions = 0
    oldest_article = 1
    max_articles_per_feed = 100
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    feeds          = [(u'International', u'http://derstandard.at/?page=rss&ressort=internationalpolitik'),
        (u'Inland', u'http://derstandard.at/?page=rss&ressort=innenpolitik'),
        (u'Wirtschaft', u'http://derstandard.at/?page=rss&ressort=investor'),
        (u'Web', u'http://derstandard.at/?page=rss&ressort=webstandard'),
        (u'Sport', u'http://derstandard.at/?page=rss&ressort=sport'),
        (u'Panorama', u'http://derstandard.at/?page=rss&ressort=panorama'),
        (u'Etat', u'http://derstandard.at/?page=rss&ressort=etat'),
        (u'Kultur', u'http://derstandard.at/?page=rss&ressort=kultur'),
        (u'Wissenschaft', u'http://derstandard.at/?page=rss&ressort=wissenschaft'),
        (u'Gesundheit', u'http://derstandard.at/?page=rss&ressort=gesundheit'),
        (u'Bildung', u'http://derstandard.at/?page=rss&ressort=subildung')]
    remove_tags = [dict(name='div'), dict(name='a'), dict(name='link'), dict(name='meta'),
        dict(name='form',attrs={'name':'sitesearch'}), dict(name='hr')]
    preprocess_regexps = [
        (re.compile(r'\[[\d]*\]', re.DOTALL|re.IGNORECASE), lambda match: ''),
        (re.compile(r'bgcolor="#\w{3,6}"', re.DOTALL|re.IGNORECASE), lambda match: '')
    ]
    
    def print_version(self, url):
        return url.replace('?id=', 'txt/?id=')

    def get_article_url(self, article):
        '''if the article links to a index page (ressort) or a picture gallery
           (ansichtssache), don't add it'''
        if (article.link.count('ressort') > 0 or article.title.lower().count('ansichtssache') > 0):
            return None
        return article.link

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
        soup.head.insert(0,mtag)
        return soup  