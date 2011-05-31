from calibre.web.feeds.news import BasicNewsRecipe

class NewsTimes(BasicNewsRecipe):
    title                 = 'Newstimes'
    __author__            = 'Darko Miletic'
    description           = 'news from USA'
    language = 'en'

    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    remove_javascript     = True

    keep_only_tags = [
                         dict(name='h1', attrs={'id':'articleTitle'})
                        ,dict(name='div', attrs={'id':['articleByline','articleDate','articleBody']})
                     ]
    remove_tags = [
                    dict(name=['object','link'])
                   ,dict(name='div', attrs={'class':'articleEmbeddedAdBox'})
                  ]

    
    feeds = [
              (u'Latest news'    , u'http://feeds.newstimes.com/mngi/rss/CustomRssServlet/3/201071.xml' )
            ]

