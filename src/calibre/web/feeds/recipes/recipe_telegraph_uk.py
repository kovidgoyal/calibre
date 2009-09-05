#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
telegraph.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class TelegraphUK(BasicNewsRecipe):
    title                 = u'Telegraph.co.uk'
    __author__            = 'Darko Miletic'
    description           = 'News from United Kingdom'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    language = 'en'

    use_embedded_content  = False

    extra_css = '''
                h1{font-family :Arial,Helvetica,sans-serif; font-size:large; }
                h2{font-family :Arial,Helvetica,sans-serif; font-size:x-small; color:#444444}
                .story{font-family :Arial,Helvetica,sans-serif; font-size: x-small;}
                .byline{color:#666666; font-family :Arial,Helvetica,sans-serif; font-size: xx-small;}
                a{color:#234B7B; }
                .imageExtras{color:#666666; font-family :Arial,Helvetica,sans-serif; font-size: xx-small;}
                '''
    
    keep_only_tags    = [ 
                           dict(name='div', attrs={'class':'storyHead'})
                          ,dict(name='div', attrs={'class':'story'    })
                          #,dict(name='div', attrs={'class':['slideshowHD gutterUnder',"twoThirds gutter","caption" ]   }) 
                        ]
    remove_tags    = [dict(name='div', attrs={'class':['related_links_inline',"imgindex","next","prev","gutterUnder"]})]
    
    feeds          = [
                         (u'UK News'        , u'http://www.telegraph.co.uk/news/uknews/rss'                                      )
                        ,(u'World News'     , u'http://www.telegraph.co.uk/news/worldnews/rss'                                   )
                        ,(u'Politics'       , u'http://www.telegraph.co.uk/news/newstopics/politics/rss'                         )
                        ,(u'Technology News', u'http://www.telegraph.co.uk/scienceandtechnology/technology/technologynews/rss'   )
                        ,(u'UK News'        , u'http://www.telegraph.co.uk/scienceandtechnology/technology/technologyreviews/rss')
                        ,(u'Science News'   , u'http://www.telegraph.co.uk/scienceandtechnology/science/sciencenews/rss'         )
                        ,(u'Sport'          , u'http://www.telegraph.co.uk/sport/rss'                                            )
                        ,(u'Earth News'     , u'http://www.telegraph.co.uk/earth/earthnews/rss'                                  )
                        ,(u'Comment'        , u'http://www.telegraph.co.uk/comment/rss'                                          )
                        ,(u'How about that?', u'http://www.telegraph.co.uk/news/newstopics/howaboutthat/rss'                     )
                     ]

    def get_article_url(self, article):
        
        url = article.get('guid', None)
        
        if 'picture-galleries' in url or 'pictures' in url or 'picturegalleries' in url :
            url = None
        
        return url

   
