from calibre.web.feeds.news import BasicNewsRecipe

class TheDailyMail(BasicNewsRecipe):
    title          = u'The Daily Mail'
    oldest_article = 2
    language = 'en'

    author = 'RufusA'
    simultaneous_downloads= 1
    max_articles_per_feed = 50

    extra_css = 'h1 {text-align: left;}'

    remove_tags = [ dict(name='ul', attrs={'class':'article-icons-links'}) ]
    remove_tags_after  = dict(name='h3', attrs={'class':'social-links-title'})
    remove_tags_before  = dict(name='div', attrs={'id':'content'})
    no_stylesheets = True
    
    feeds          = [
	(u'Home', u'http://www.dailymail.co.uk/home/index.rss'),
	(u'News', u'http://www.dailymail.co.uk/news/index.rss'),
	(u'Sport', u'http://www.dailymail.co.uk/sport/index.rss'),
	(u'TV and Showbiz', u'http://www.dailymail.co.uk/tvshowbiz/index.rss'),
	(u'Femail', u'http://www.dailymail.co.uk/femail/index.rss'),
	(u'Health', u'http://www.dailymail.co.uk/health/index.rss'),
	(u'Science and Technology', u'http://www.dailymail.co.uk/sciencetech/index.rss'),
	(u'Money', u'http://www.dailymail.co.uk/money/index.rss'),
	(u'Property', u'http://www.dailymail.co.uk/property/index.rss'),
	(u'Motoring', u'http://www.dailymail.co.uk/motoring/index.rss'),
	(u'Travel', u'http://www.dailymail.co.uk/travel/index.rss')]

    def print_version(self, url):
        main = url.partition('?')[0]
        return main + '?printingPage=true'
