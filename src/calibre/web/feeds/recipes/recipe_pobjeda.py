#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
pobjeda.co.me
'''

import re
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class Pobjeda(BasicNewsRecipe):
    title                 = 'Pobjeda Online'
    __author__            = 'Darko Miletic'
    description           = 'News from Montenegro'
    publisher             = 'Pobjeda a.d.'
    category              = 'news, politics, Montenegro'    
    no_stylesheets        = True
    remove_javascript     = True
    encoding              = 'utf8'
    remove_javascript     = True
    use_embedded_content  = False
    INDEX                 = u'http://www.pobjeda.co.me'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"'

    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'class':'vijest'})]

    remove_tags = [dict(name=['object','link'])]

    feeds = [
               (u'Politika'          , u'http://www.pobjeda.co.me/rubrika.php?rubrika=1'  )
              ,(u'Ekonomija'         , u'http://www.pobjeda.co.me/rubrika.php?rubrika=2'  )
              ,(u'Drustvo'           , u'http://www.pobjeda.co.me/rubrika.php?rubrika=3'  )
              ,(u'Crna Hronika'      , u'http://www.pobjeda.co.me/rubrika.php?rubrika=4'  )
              ,(u'Kultura'           , u'http://www.pobjeda.co.me/rubrika.php?rubrika=5'  )
              ,(u'Hronika Podgorice' , u'http://www.pobjeda.co.me/rubrika.php?rubrika=7'  )
              ,(u'Feljton'           , u'http://www.pobjeda.co.me/rubrika.php?rubrika=8'  )
              ,(u'Crna Gora'         , u'http://www.pobjeda.co.me/rubrika.php?rubrika=9'  )
              ,(u'Svijet'            , u'http://www.pobjeda.co.me/rubrika.php?rubrika=202')
              ,(u'Ekonomija i Biznis', u'http://www.pobjeda.co.me/dodatak.php?rubrika=11' )
              ,(u'Djeciji Svijet'    , u'http://www.pobjeda.co.me/dodatak.php?rubrika=12' )
              ,(u'Kultura i Drustvo' , u'http://www.pobjeda.co.me/dodatak.php?rubrika=13' )
              ,(u'Agora'             , u'http://www.pobjeda.co.me/dodatak.php?rubrika=133')
              ,(u'Ekologija'         , u'http://www.pobjeda.co.me/dodatak.php?rubrika=252')
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = 'sr-Latn-ME'
        soup.html['lang']     = 'sr-Latn-ME'
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-ME"/>'
        soup.head.insert(0,mtag)
        return soup

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        cover_item = soup.find('img',attrs={'alt':'Naslovna strana'})
        if cover_item:
           cover_url = self.INDEX + cover_item.parent['href']
        return cover_url
    
    def parse_index(self):
        totalfeeds = []
        lfeeds = self.get_feeds()
        for feedobj in lfeeds:
            feedtitle, feedurl = feedobj
            self.report_progress(0, _('Fetching feed')+' %s...'%(feedtitle if feedtitle else feedurl))             
            articles = []
            soup = self.index_to_soup(feedurl)        
            for item in soup.findAll('div', attrs={'class':'vijest'}):
                description = self.tag_to_string(item.h2)
                atag = item.h1.find('a')
                if atag and atag.has_key('href'):
                    url         = self.INDEX + '/' + atag['href']
                    title       = self.tag_to_string(atag)
                    date        = strftime(self.timefmt)                
                    articles.append({
                                      'title'      :title
                                     ,'date'       :date
                                     ,'url'        :url
                                     ,'description':description
                                    })
            totalfeeds.append((feedtitle, articles))
        return totalfeeds
        
