#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
theonion.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TheOnion(BasicNewsRecipe):
    title                 = 'The Onion'
    __author__            = 'Darko Miletic'
    description           = "America's finest news source"    
    oldest_article        = 2    
    max_articles_per_feed = 100
    publisher             = u'Onion, Inc.'
    category              = u'humor, news, USA'    
    language = 'en'

    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    remove_javascript     = True
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
     
    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , category
                        , '--publisher'     , publisher
                        ]

    keep_only_tags = [dict(name='div', attrs={'id':'main'})]
    
    remove_tags = [
                     dict(name=['object','link','iframe','base'])
                    ,dict(name='div', attrs={'class':['toolbar_side','graphical_feature','toolbar_bottom']})
                    ,dict(name='div', attrs={'id':['recent_slider','sidebar','pagination','related_media']})
                  ]

                            
    feeds = [
              (u'Daily'  , u'http://feeds.theonion.com/theonion/daily' )
             ,(u'Sports' , u'http://feeds.theonion.com/theonion/sports' )
            ]
