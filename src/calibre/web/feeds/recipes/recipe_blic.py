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
    language = 'sr'

    lang                  = 'sr-Latn-RS'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif} '
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        }
        
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'class':'single_news'})]

    feeds              = [(u'Vesti', u'http://www.blic.rs/rssall.php')]

    remove_tags        = [dict(name=['object','link'])]
    
    def print_version(self, url):
        rest_url = url.partition('?')[2]
        return u'http://www.blic.rs/_print.php?' + rest_url

    def preprocess_html(self, soup):
        attribs = [  'style','font','valign'
                    ,'colspan','width','height'
                    ,'rowspan','summary','align'
                    ,'cellspacing','cellpadding'
                    ,'frames','rules','border'
                  ]
        for item in soup.body.findAll(name=['table','td','tr','th','caption','thead','tfoot','tbody','colgroup','col']):
            item.name = 'div'
            for attrib in attribs:
                if item.has_key(attrib):
                   del item[attrib]                        
        return self.adeify_images(soup)

    def get_article_url(self, article):
        raw = article.get('link',  None)         
        return raw.replace('.co.yu','.rs')
        