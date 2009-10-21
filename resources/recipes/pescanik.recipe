#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
pescanik.net
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Pescanik(BasicNewsRecipe):
    title                 = 'Pescanik'
    __author__            = 'Darko Miletic'
    description           = 'Pescanik'
    publisher             = 'Pescanik'
    category              = 'news, politics, Serbia'
    oldest_article        = 5
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    language = 'sr'

    lang                  = 'sr-Latn-RS'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif} .contentheading{font-size: x-large; font-weight: bold} .small{font-size: small} .createdate{font-size: x-small; font-weight: bold}'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }


    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    remove_tags = [
                     dict(name='td'  , attrs={'class':'buttonheading'})
                    ,dict(name='span', attrs={'class':'article_seperator'})
                    ,dict(name=['object','link','h4','ul'])
                  ]

    feeds       = [(u'Pescanik Online', u'http://www.pescanik.net/index.php?option=com_rd_rss&id=12')]

    def print_version(self, url):
        nurl = url.replace('/index.php','/index2.php')
        return nurl + '&pop=1&page=0'

    def preprocess_html(self, soup):
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        soup.head.insert(0,mlang)
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
