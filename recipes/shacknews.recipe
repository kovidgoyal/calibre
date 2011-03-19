
from calibre.web.feeds.news import BasicNewsRecipe

class Shacknews(BasicNewsRecipe):
    __author__  = 'Docbrown00'
    __license__   = 'GPL v3'
    title          = u'Shacknews'
    oldest_article = 7
    max_articles_per_feed = 100
    language = 'en'

    no_stylesheets = True
    remove_tags = [dict(name='div', attrs={'class': ['nuggets', 'comments']}), 
	        dict(name='p', attrs={'class': 'videoembed'})]
    keep_only_tags = [dict(name='div', attrs={'class':'story'})]
    feeds          = [
		(u'Latest News', u'http://feed.shacknews.com/shackfeed.xml'),
		(u'PC', u'http://feed.shacknews.com/extras/tag_rss.x/PC'),
		(u'Wii', u'http://feed.shacknews.com/extras/tag_rss.x/Nintendo+Wii'),
		(u'Xbox 360', u'http://feed.shacknews.com/extras/tag_rss.x/Xbox+360'),
		(u'Playstation 3', u'http://feed.shacknews.com/extras/tag_rss.x/PlayStation+3'),
		(u'PSP', u'http://feed.shacknews.com/extras/tag_rss.x/PSP'),
		(u'Nintendo DS', u'http://feed.shacknews.com/extras/tag_rss.x/Nintendo+DS'),
		(u'iPhone', u'http://feed.shacknews.com/extras/tag_rss.x/iPhone'),
		(u'DLC', u'http://feed.shacknews.com/extras/tag_rss.x/DLC'),
		(u'Valve', u'http://feed.shacknews.com/extras/tag_rss.x/Valve'),
		(u'Electronic Arts', u'http://feed.shacknews.com/extras/tag_rss.x/Electronic+Arts')
	     ]
