#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
nin.co.yu
'''

import re, urllib
from calibre.web.feeds.news import BasicNewsRecipe

class Nin(BasicNewsRecipe):    
    title                  = 'NIN online'
    __author__             = 'Darko Miletic'
    description            = 'Nedeljne informativne novine'
    publisher              = 'NIN'
    category               = 'news, politics, Serbia'    
    no_stylesheets         = True
    oldest_article         = 15
    simultaneous_downloads = 1
    delay                  = 1
    encoding               = 'utf8'
    needs_subscription     = True
    PREFIX                 = 'http://www.nin.co.yu'
    INDEX                  = PREFIX + '/?change_lang=ls'
    LOGIN                  = PREFIX + '/?logout=true'
    remove_javascript      = True
    use_embedded_content   = False
    language              = _('Serbian')
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 
                          
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
    feeds             =[(u'NIN', u'http://www.nin.co.yu/misc/rss.php?feed=RSS2.0')]
    
    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        link_item = soup.find('img',attrs={'width':'100','height':'137','border':'0'})
        if link_item:
           cover_url = self.PREFIX + link_item['src']
        return cover_url

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-RS"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
