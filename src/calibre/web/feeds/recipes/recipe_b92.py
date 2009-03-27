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
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'cp1250'
    language              = _('Serbian')
    extra_css             = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em}"' 
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    keep_only_tags     = [dict(name='table', attrs={'class':'maindocument'})]

    remove_tags = [
                     dict(name='ul', attrs={'class':'comment-nav'})
                    ,dict(name=['embed','link','base']            )
                  ]

    feeds          = [
                        (u'Vesti', u'http://www.b92.net/info/rss/vesti.xml')
                       ,(u'Biz'  , u'http://www.b92.net/info/rss/biz.xml'  )
                     ]

    def print_version(self, url):
        return url + '&version=print'

    def preprocess_html(self, soup):
        del soup.body['onload']
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(align=True):
            del item['align']
        for item in soup.findAll('font'):
            item.name='p'
            if item.has_key('size'):
               del item['size']
        return soup
