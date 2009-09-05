#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
nin.co.rs
'''

import re, urllib
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Nin(BasicNewsRecipe):    
    title                  = 'NIN online'
    __author__             = 'Darko Miletic'
    description            = 'Nedeljne informativne novine'
    publisher              = 'NIN D.O.O.'
    category               = 'news, politics, Serbia'    
    no_stylesheets         = True
    oldest_article         = 15
    simultaneous_downloads = 1
    delay                  = 1
    encoding               = 'utf-8'
    needs_subscription     = True
    PREFIX                 = 'http://www.nin.co.rs'
    INDEX                  = PREFIX + '/?change_lang=ls'
    LOGIN                  = PREFIX + '/?logout=true'
    FEED                   = PREFIX + '/misc/rss.php?feed=RSS2.0'
    use_embedded_content   = False
    language = 'sr'

    lang                   = 'sr-Latn-RS'
    direction              = 'ltr'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif} .artTitle{font-size: x-large; font-weight: bold} .columnhead{font-size: small; font-weight: bold}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }
                          
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.INDEX)
        if self.username is not None and self.password is not None:
            data = urllib.urlencode({ 'login_name':self.username
                                     ,'login_password':self.password
                                     ,'imageField.x':'32'
                                     ,'imageField.y':'15'                                 
                                   })
            br.open(self.LOGIN,data)
        return br

    keep_only_tags    =[dict(name='td', attrs={'width':'520'})]
    remove_tags_after =dict(name='html')
    feeds             =[(u'NIN', FEED)]
    
    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        link_item = soup.find('img',attrs={'width':'100','height':'137','border':'0'})
        if link_item:
           cover_url = self.PREFIX + link_item['src']
        return cover_url

    def preprocess_html(self, soup):
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)        
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

    def get_article_url(self, article):
        raw = article.get('link',  None)         
        return raw.replace('.co.yu','.co.rs')
