from calibre.web.feeds.news import BasicNewsRecipe

class AdvancedUserRecipe1234144423(BasicNewsRecipe):
    title          = u'Indianapolis Star'
    oldest_article = 5
    language = 'en'

    __author__     = 'Owen Kelly'
    max_articles_per_feed = 100

    cover_url  = u'http://www2.indystar.com/frontpage/images/today.jpg'
    
    feeds          = [(u'Community Headlines', u'http://www.indystar.com/apps/pbcs.dll/section?Category=LOCAL&template=rss&mime=XML'), (u'News Headlines', u'http://www.indystar.com/apps/pbcs.dll/section?Category=NEWS&template=rss&mime=XML'), (u'Business Headlines', u'http://www..indystar.com/apps/pbcs.dll/section?Category=BUSINESS&template=rss&mime=XML'), (u'Sports Headlines', u'http://www.indystar.com/apps/pbcs.dll/section?Category=SPORTS&template=rss&mime=XML'), (u'Lifestyle Headlines', u'http://www.indystar.com/apps/pbcs.dll/section?Category=LIVING&template=rss&mime=XML'), (u'Opinion Headlines', u'http://www.indystar.com/apps/pbcs.dll/section?Category=OPINION&template=rss&mime=XML')]

    def print_version(self, url):
        return url + '&template=printart'