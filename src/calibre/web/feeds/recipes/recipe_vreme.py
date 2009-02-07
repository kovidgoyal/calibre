#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
vreme.com
'''

import re
from calibre import strftime

from calibre.web.feeds.news import BasicNewsRecipe

class Vreme(BasicNewsRecipe):    
    title          = 'Vreme'
    __author__     = 'Darko Miletic'
    description    = 'Politicki Nedeljnik Srbije'
    publisher      = 'Vreme d.o.o.'
    category       = 'news, politics, Serbia'    
    no_stylesheets = True
    remove_javascript  = True
    needs_subscription = True    
    INDEX = 'http://www.vreme.com'
    LOGIN = 'http://www.vreme.com/account/index.php'
    remove_javascript     = True
    use_embedded_content  = False
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "monospace1";src:url(res:///opt/sony/ebook/FONT/tt0419m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: left; font-family: serif1, serif} .article_date{font-family: monospace1, monospace} .article_description{font-family: sans1, sans-serif} .navbar{font-family: monospace1, monospace}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
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

    remove_tags = [
                    dict(name=['object','link'])
                   ,dict(name='table',attrs={'xclass':'image'})
                  ]
        
    def print_version(self, url):
        return url + '&print=yes'

    def preprocess_html(self, soup):
        del soup.body['text'   ]
        del soup.body['bgcolor']
        del soup.body['onload' ]
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn"/>'
        soup.head.insert(0,mtag)
        tbl = soup.body.table
        tbbb = soup.find('td')
        if tbbb:
           tbbb.extract()
           tbl.extract()
           soup.body.insert(0,tbbb)
        return soup
                
    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        cover_item = soup.find('img',attrs={'alt':'Naslovna strana broja'})
        if cover_item:
           cover_url = self.INDEX + cover_item['src']
        return cover_url

    language              = _('Serbian')