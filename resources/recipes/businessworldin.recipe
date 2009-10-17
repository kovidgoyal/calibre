#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.businessworld.in
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class BusinessWorldMagazine(BasicNewsRecipe):
    title                = 'Business World Magazine'
    __author__           = 'Darko Miletic'
    description          = 'News from India'
    publisher            = 'ABP Pvt Ltd Publication'
    category             = 'news, politics, finances, India, Asia'
    delay                = 1
    no_stylesheets       = True
    INDEX                = 'http://www.businessworld.in/bw/Magazine_Current_Issue'
    ROOT                 = 'http://www.businessworld.in'
    use_embedded_content = False
    encoding             = 'utf-8'
    language             = 'en_IN'


    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : language
                        }

    def is_in_list(self,linklist,url):
        for litem in linklist:
            if litem == url:
               return True
        return False
    
    
    def parse_index(self):
        articles = []
        linklist = []
        soup = self.index_to_soup(self.INDEX)

        for item in soup.findAll('div', attrs={'class':'nametitle'}):
            description = ''
            title_prefix = ''
            feed_link = item.find('a')
            if feed_link and feed_link.has_key('href'):
                url   = self.ROOT + feed_link['href']
                if not self.is_in_list(linklist,url):
                    title = title_prefix + self.tag_to_string(feed_link)
                    date  = strftime(self.timefmt)
                    articles.append({
                                      'title'      :title
                                     ,'date'       :date
                                     ,'url'        :url
                                     ,'description':description
                                    })
                    linklist.append(url)
        return [(soup.head.title.string, articles)]

    
    keep_only_tags = [dict(name='div', attrs={'id':['register-panel','printwrapper']})]
    remove_tags = [dict(name=['object','link'])]

    def print_version(self, url):
        return url.replace('/bw/','/bw/storyContent/')

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        cover_item = soup.find('img',attrs={'class':'toughbor'})
        if cover_item:
           cover_url = self.ROOT + cover_item['src']
        return cover_url
