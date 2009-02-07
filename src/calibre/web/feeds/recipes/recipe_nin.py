#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
nin.co.yu
'''

import re, urllib
from calibre.web.feeds.news import BasicNewsRecipe

class Nin(BasicNewsRecipe):
    title                  = 'NIN online'
    __author__             = 'Darko Miletic'
    description            = 'Nedeljne informativne novine'
    no_stylesheets         = True
    oldest_article         = 15
    language              = _('Serbian')
    simultaneous_downloads = 1
    delay                  = 1
    encoding               = 'utf8'
    needs_subscription     = True
    PREFIX                 = 'http://www.nin.co.yu'
    INDEX                  = PREFIX + '/?change_lang=ls'
    LOGIN                  = PREFIX + '/?logout=true'
    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, politics, Serbia'
                        , '--publisher'     , 'NIN'
                        ]
                          
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
