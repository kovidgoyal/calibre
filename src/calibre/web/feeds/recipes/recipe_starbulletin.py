#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
starbulletin.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Starbulletin(BasicNewsRecipe):
    title                 = 'Honolulu Star-Bulletin'
    __author__            = 'Darko Miletic'
    description           = "Latest national and local Hawaii sports news"
    publisher             = 'Honolulu Star-Bulletin'
    category              = 'news, Honolulu, Hawaii'
    oldest_article        = 2
    max_articles_per_feed = 100
    language = 'en'

    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf8'
    remove_javascript     = True
    cover_url             = 'http://media.starbulletin.com/designimages/spacer.gif'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , category
                        , '--publisher'     , publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'
    
    keep_only_tags = [ dict(name='div', attrs={'id':'storyColoumn'}) ]

    remove_tags = [
                    dict(name=['object','link'])
                   ,dict(name='span', attrs={'id':'printdesc'})
                   ,dict(name='div' , attrs={'class':'lightGreyBox storyTools clearAll'})
                   ,dict(name='div' , attrs={'id':'breadcrumbs'})                    
                  ]
                        
    feeds = [
              (u'Headlines', u'http://www.starbulletin.com/starbulletin_headlines.rss' )
             ,(u'News', u'http://www.starbulletin.com/news/index.rss' )
             ,(u'Sports', u'http://www.starbulletin.com/sports/index.rss' )
             ,(u'Features', u'http://www.starbulletin.com/features/index.rss' )
             ,(u'Editorials', u'http://www.starbulletin.com/editorials/index.rss' )
             ,(u'Business', u'http://www.starbulletin.com/business/index.rss' )
             ,(u'Travel', u'http://www.starbulletin.com/travel/index.rss' )
            ]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        mtag = '\n<meta http-equiv="Content-Language" content="en"/>\n'
        soup.head.insert(0,mtag)
        return soup
        
