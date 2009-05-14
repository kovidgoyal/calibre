#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
blic.rs
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Blic(BasicNewsRecipe):
    title                 = 'Blic'
    __author__            = 'Darko Miletic'
    description           = 'Blic.co.yu online verzija najtiraznije novine u Srbiji donosi najnovije vesti iz Srbije i sveta, komentare, politicke analize, poslovne i ekonomske vesti, vesti iz regiona, intervjue, informacije iz kulture, reportaze, pokriva sve sportske dogadjaje, detaljan tv program, nagradne igre, zabavu, fenomenalni Blic strip, dnevni horoskop, arhivu svih dogadjaja'    
    publisher             = 'RINGIER d.o.o.'
    category              = 'news, politics, Serbia'
    delay                 = 1
    oldest_article        = 2
    max_articles_per_feed = 100
    remove_javascript     = True
    no_stylesheets        = True
    use_embedded_content  = False
    language              = _('Serbian')
    lang                  = 'sr-Latn-RS'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif} '
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} "' 
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'class':'single_news'})]

    feeds              = [(u'Vesti', u'http://www.blic.rs/rssall.php')]

    remove_tags        = [dict(name=['object','link'])]
    
    def print_version(self, url):
        start_url, question, rest_url = url.partition('?')
        return u'http://www.blic.rs/_print.php?' + rest_url

    def preprocess_html(self, soup):
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        soup.head.insert(0,mlang)
        for item in soup.findAll(style=True):
            del item['style']
        return self.adeify_images(soup)

    def get_article_url(self, article):
        raw = article.get('link',  None)         
        return raw.replace('.co.yu','.rs')
        