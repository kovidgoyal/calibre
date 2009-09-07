#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
miamiherald.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheMiamiHerald(BasicNewsRecipe):
    title                 = 'The Miami Herald'
    __author__            = 'Darko Miletic'
    description           = "Miami-Dade and Broward's source for the latest breaking local news on sports, weather, business, jobs, real estate, shopping, health, travel, entertainment, & more."    
    oldest_article        = 1    
    max_articles_per_feed = 100
    publisher             = u'The Miami Herald'
    category              = u'miami herald, weather, dolphins, news, miami news, local news, miamiherald, miami newspaper, miamiherald.com, miami, the miami herald, broward, miami-dade'    
    language = 'en'
    
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    remove_javascript     = True
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , category
                        , '--publisher'     , publisher
                        ]

                        
    keep_only_tags = [dict(name='div', attrs={'id':'pageContainer'})]
                        
    feeds = [ 
              (u'Breaking News'  , u'http://www.miamiherald.com/416/index.xml' )
             ,(u'Miami-Dade' , u'http://www.miamiherald.com/460/index.xml' )
             ,(u'Broward' , u'http://www.miamiherald.com/467/index.xml' )
             ,(u'Florida Keys' , u'http://www.miamiherald.com/505/index.xml' )
             ,(u'Florida' , u'http://www.miamiherald.com/569/index.xml' )
             ,(u'Nation' , u'http://www.miamiherald.com/509/index.xml' )
             ,(u'World' , u'http://www.miamiherald.com/578/index.xml' )
             ,(u'Americas' , u'http://www.miamiherald.com/579/index.xml' )
             ,(u'Cuba' , u'http://www.miamiherald.com/581/index.xml' )
             ,(u'Haiti' , u'http://www.miamiherald.com/582/index.xml' )
             ,(u'Politics' , u'http://www.miamiherald.com/515/index.xml' )
             ,(u'Education' , u'http://www.miamiherald.com/295/index.xml' )
             ,(u'Environment' , u'http://www.miamiherald.com/573/index.xml' )
            ]
            
    def print_version(self, url):
        return url.replace('/story/','/v-print/story/')
        
