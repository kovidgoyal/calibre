#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
borba.rs
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class Borba(BasicNewsRecipe):
    title                 = 'Borba Online'
    __author__            = 'Darko Miletic'
    description           = 'Dnevne novine Borba Online'
    publisher             = 'IP Novine Borba'
    category              = 'news, politics, Serbia'    
    language              = _('Serbian')
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf8'
    remove_javascript     = True
    use_embedded_content  = False
    cover_url             = 'http://www.borba.rs/images/stories/novine/naslovna_v.jpg'
    INDEX                 = u'http://www.borba.rs/'
    extra_css = '@font-face {font-family: "serif0";src:url(res:///Data/FONT/serif0.ttf)} @font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif0, serif1, serif} .article_description{font-family: serif0, serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'class':'main'})]

    remove_tags_after = dict(name='div',attrs={'id':'written_comments_title'})
 
    remove_tags = [
                     dict(name=['object','link','iframe','base','img'])
                    ,dict(name='div',attrs={'id':'written_comments_title'})
                  ]

    feeds = [
               (u'Najnovije vesti', u'http://www.borba.rs/content/blogsection/28/105/')
              ,(u'Prvi plan'      , u'http://www.borba.rs/content/blogsection/4/92/'  )
              ,(u'Dogadjaji'      , u'http://www.borba.rs/content/blogsection/21/83/' )
              ,(u'Ekonomija'      , u'http://www.borba.rs/content/blogsection/5/35/'  )
              ,(u'Komentari'      , u'http://www.borba.rs/content/blogsection/23/94/' )
              ,(u'Svet'           , u'http://www.borba.rs/content/blogsection/7/36/'  )
              ,(u'Sport'          , u'http://www.borba.rs/content/blogsection/6/37/'  )
              ,(u'Fama'           , u'http://www.borba.rs/content/blogsection/25/89/' )
              ,(u'B2 Dodatak'     , u'http://www.borba.rs/content/blogsection/30/116/')
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-ME'
        soup.html['lang']     = 'sr-Latn-ME'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-ME"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(font=True):
            del item['font']
        return soup

    def parse_index(self):
        totalfeeds = []
        lfeeds = self.get_feeds()
        for feedobj in lfeeds:
            feedtitle, feedurl = feedobj
            self.report_progress(0, _('Fetching feed')+' %s...'%(feedtitle if feedtitle else feedurl))
            articles = []
            soup = self.index_to_soup(feedurl)
            for item in soup.findAll('a', attrs={'class':'contentpagetitle'}):
                url         = item['href']
                title       = self.tag_to_string(item)
                articles.append({
                                      'title'      :title
                                     ,'date'       :''
                                     ,'url'        :url
                                     ,'description':''
                                    })
            totalfeeds.append((feedtitle, articles))
        return totalfeeds
        
