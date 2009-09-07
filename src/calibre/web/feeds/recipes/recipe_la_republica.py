from calibre.web.feeds.news import BasicNewsRecipe

class LaRepublica(BasicNewsRecipe):
    title          = u'la Repubblica'
    oldest_article = 1
    language = 'it'

    author = 'Darko Miletic'
    max_articles_per_feed = 100
    remove_javascript = True
    no_stylesheets = True
    
    keep_only_tags     = [dict(name='div', attrs={'class':'articolo'})]


    remove_tags        = [
                            dict(name=['object','link'])
                           ,dict(name='span',attrs={'class':'linkindice'})
                           ,dict(name='div',attrs={'class':'bottom-mobile'})
                           ,dict(name='div',attrs={'id':['rssdiv','blocco']})
                         ]
    
    feeds          = [
                       (u'Repubblica homepage', u'http://www.repubblica.it/rss/homepage/rss2.0.xml'),
                       (u'Repubblica Scienze', u'http://www.repubblica.it/rss/scienze/rss2.0.xml'),
                       (u'Repubblica Tecnologia', u'http://www.repubblica.it/rss/tecnologia/rss2.0.xml'),
                       (u'Repubblica Esteri', u'http://www.repubblica.it/rss/esteri/rss2.0.xml')
                     ]

