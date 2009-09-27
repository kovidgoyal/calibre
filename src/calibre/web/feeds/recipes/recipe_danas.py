#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
danas.rs
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Danas(BasicNewsRecipe):
    title                 = 'Danas'
    __author__            = 'Darko Miletic'
    description           = 'Vesti'
    publisher             = 'Danas d.o.o.'
    category              = 'news, politics, Serbia'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = False
    use_embedded_content  = False
    language              = 'sr'
    lang                  = 'sr-Latn-RS'
    direction             = 'ltr'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : language
                        , 'pretty_print'     : True
                        }


    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'id':'left'})]
    remove_tags = [
                     dict(name='div', attrs={'class':['width_1_4','metaClanka','baner']})
                    ,dict(name='div', attrs={'id':'comments'})
                    ,dict(name=['object','link'])
                  ]

    feeds          = [ 
                        (u'Vesti'   , u'http://www.danas.rs/rss/rss.asp'            )
                       ,(u'Periskop', u'http://www.danas.rs/rss/rss.asp?column_id=4')
                     ]

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
        return soup
