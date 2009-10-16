#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
b92.net
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class B92(BasicNewsRecipe):
    title                 = 'B92'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne vesti iz Srbije i sveta'    
    publisher             = 'B92'
    category              = 'news, politics, Serbia'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1250'
    language = 'sr'

    lang                  = 'sr-Latn-RS'
    extra_css             = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        }
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    keep_only_tags     = [dict(name='table', attrs={'class':'maindocument'})]

    remove_tags = [
                     dict(name='ul', attrs={'class':'comment-nav'})
                    ,dict(name=['embed','link','base']            )
                    ,dict(name='div', attrs={'class':'udokum'}    )
                  ]

    feeds          = [
                        (u'Vesti', u'http://www.b92.net/info/rss/vesti.xml')
                       ,(u'Biz'  , u'http://www.b92.net/info/rss/biz.xml'  )
                     ]

    def print_version(self, url):
        return url + '&version=print'

    def preprocess_html(self, soup):
        del soup.body['onload']
        for item in soup.findAll('font'):
            item.name='div'
            if item.has_key('size'):
               del item['size']
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
