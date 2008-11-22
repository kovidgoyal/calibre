#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
vreme.com
'''

import string
import locale
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
    #Locale setting to get appropriate date/month values in Serbian if possible
    try:
      #Windows seting for locale
      locale.setlocale(locale.LC_TIME,'Serbian (Latin)')
    except locale.Error:
      #Linux setting for locale -- choose one appropriate for your distribution
      try:
        locale.setlocale(locale.LC_TIME,'sr_YU')
      except locale.Error:
        try:
          locale.setlocale(locale.LC_TIME,'sr_CS@Latn')
        except locale.Error:
          try:
            locale.setlocale(locale.LC_TIME,'sr@Latn')
          except locale.Error:
            try:
              locale.setlocale(locale.LC_TIME,'sr_Latn')
            except locale.Error:
              try:
                locale.setlocale(locale.LC_TIME,'sr_RS')
              except locale.Error:                  
                locale.setlocale(locale.LC_TIME,'C')

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
            feed_link = item.find('a')
            if feed_link and feed_link.has_key('href'):
                url = self.INDEX+feed_link['href']+'&print=yes'
                title = self.tag_to_string(feed_link)
                date = strftime('%A, %d %B, %Y')
                description = ''
                articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':description
                                })
        return [(soup.head.title.string, articles)]