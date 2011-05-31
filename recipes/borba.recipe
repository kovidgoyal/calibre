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
    language = 'sr'

    lang                  = _('sr-Latn-RS')
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    cover_url             = 'http://www.borba.rs/images/stories/novine/naslovna_v.jpg'
    INDEX                 = u'http://www.borba.rs/'
    extra_css = ' @font-face {font-family: "serif1"; src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif} .contentheading{font-size: x-large; font-weight: bold} .createdate{font-size: small; font-weight: bold} '
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }
     
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
        
