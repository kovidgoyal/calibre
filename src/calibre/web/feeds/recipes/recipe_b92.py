#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
b92.net
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe

class B92(BasicNewsRecipe):
    title                 = 'B92'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne vesti iz Srbije i sveta'    
    oldest_article        = 2
    publisher             = 'B92.net'
    category              = 'news, politics, Serbia'    
    max_articles_per_feed = 100
    remove_javascript     = True
    no_stylesheets        = True
    use_embedded_content  = False
    cover_url = 'http://static.b92.net/images/fp/logo.gif'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "monospace1";src:url(res:///opt/sony/ebook/FONT/tt0419m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: left; font-family: serif1, serif} .article_date{font-family: monospace1, monospace} .article_description{font-family: sans1, sans-serif} .navbar{font-family: monospace1, monospace}'

    keep_only_tags = [ dict(name='div', attrs={'class':'sama_vest'}) ]
        
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    feeds          = [
                        (u'Vesti', u'http://www.b92.net/info/rss/vesti.xml')
                       ,(u'Biz'  , u'http://www.b92.net/info/rss/biz.xml'  )
                       ,(u'Zivot', u'http://www.b92.net/info/rss/zivot.xml')
                       ,(u'Sport', u'http://www.b92.net/info/rss/sport.xml')
                     ]

    def print_version(self, url):
        main, sep, article_id = url.partition('nav_id=')
        rmain, rsep, rrest = main.partition('.php?')
        mrmain , rsepp, nnt = rmain.rpartition('/')
        mprmain, rrsep, news_type = mrmain.rpartition('/')
        nurl = 'http://www.b92.net/mobilni/' + news_type + '/index.php?nav_id=' + article_id
        brbiz, biz, bizrest = rmain.partition('/biz/')
        if biz:
            nurl = 'http://www.b92.net/mobilni/biz/index.php?nav_id=' + article_id
        return nurl

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn'
        soup.html['lang']     = 'sr-Latn'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(name='img',align=True):
            del item['align']
            item.insert(0,'<br /><br />')
        return soup
    language = _('Serbian')