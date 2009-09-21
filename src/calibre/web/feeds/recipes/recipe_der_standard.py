#!/usr/bin/env  python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Gerhard Aigner <gerhard.aigner at gmail.com>'

''' http://www.derstandard.at - Austrian Newspaper '''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class DerStandardRecipe(BasicNewsRecipe):
    title = u'derStandard'
    __author__ = 'Gerhard Aigner and Sujata Raman'
    description = u'Nachrichten aus ??sterreich'
    publisher ='derStandard.at'
    category = 'news, politics, nachrichten, Austria'
    use_embedded_content = False
    remove_empty_feeds = True
    lang = 'de-AT'
    no_stylesheets = True
    encoding = 'utf-8'
    language = 'de'

    oldest_article = 1
    max_articles_per_feed = 100

    extra_css = '''
                .artikelBody{font-family:Arial,Helvetica,sans-serif;}
                .artikelLeft{font-family:Arial,Helvetica,sans-serif;font-size:x-small;}
                h4{color:#404450;font-size:x-small;}
                h6{color:#404450; font-size:x-small;}
                '''
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
        (u'Bildung', u'http://derstandard.at/?page=rss&ressort=subildung')
                      ]

    keep_only_tags = [
                        dict(name='div', attrs={'class':["artikel","artikelLeft","artikelBody"]}) ,
                         ]

    remove_tags = [
                    dict(name='link'), dict(name='meta'),dict(name='iframe'),dict(name='style'),
                    dict(name='form',attrs={'name':'sitesearch'}), dict(name='hr'),
                    dict(name='div', attrs={'class':["diashow"]})]
    preprocess_regexps = [
        (re.compile(r'\[[\d]*\]', re.DOTALL|re.IGNORECASE), lambda match: ''),
        (re.compile(r'bgcolor="#\w{3,6}"', re.DOTALL|re.IGNORECASE), lambda match: '')
    ]

    filter_regexps = [r'/r[1-9]*']

    def get_article_url(self, article):
        '''if the article links to a index page (ressort) or a picture gallery
           (ansichtssache), don't add it'''
        if ( article.link.count('ressort') > 0 or article.title.lower().count('ansichtssache') > 0 ):
            return None
        matchObj = re.search( re.compile(r'/r'+'[1-9]*',flags=0), article.link,flags=0)

        if matchObj:
            return None

        return article.link

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
        soup.head.insert(0,mtag)

        for t in soup.findAll(['ul', 'li']):
            t.name = 'div'
        return soup
