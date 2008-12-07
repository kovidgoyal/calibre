#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
vreme.com
'''

import string,re
from calibre import strftime
from calibre.web.feeds.recipes import BasicNewsRecipe

class Vreme(BasicNewsRecipe):
    
    title       = 'Vreme'
    __author__  = 'Darko Miletic'
    description = 'Politicki Nedeljnik Srbije'
    timefmt = ' [%A, %d %B, %Y]'
    no_stylesheets = True
    simultaneous_downloads = 1
    delay = 1
    needs_subscription = True
    INDEX = 'http://www.vreme.com'
    LOGIN = 'http://www.vreme.com/account/index.php'

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open(self.LOGIN)
            br.select_form(name='f')
            br['username'] = self.username
            br['password'] = self.password
            br.submit()
        return br
    
    def parse_index(self):
        articles = []
        soup = self.index_to_soup(self.INDEX)
        
        for item in soup.findAll('span', attrs={'class':'toc2'}):
            description = ''
            title_prefix = ''

            descript_title_tag = item.findPreviousSibling('span', attrs={'class':'toc1'})
            if descript_title_tag:
               title_prefix = self.tag_to_string(descript_title_tag) + ' '

            descript_tag = item.findNextSibling('span', attrs={'class':'toc3'})
            if descript_tag:
               description = self.tag_to_string(descript_tag)
               
            feed_link = item.find('a')
            if feed_link and feed_link.has_key('href'):
                url   = self.INDEX + feed_link['href']
                title = title_prefix + self.tag_to_string(feed_link)
                date  = strftime(self.timefmt)                
                articles.append({
                                  'title'      :title
                                 ,'date'       :date
                                 ,'url'        :url
                                 ,'description':description
                                })
        return [(soup.head.title.string, articles)]
        
    def print_version(self, url):
        return url + '&print=yes'
