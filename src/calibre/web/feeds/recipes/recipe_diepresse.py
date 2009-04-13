import re

from calibre.web.feeds.news import BasicNewsRecipe

class DiePresseRecipe(BasicNewsRecipe):
    title          = u'diePresse'
    oldest_article = 1
    max_articles_per_feed = 100
    recursions = 0
    language = _('German')
    __author__ = 'Gerhard Aigner'

    preprocess_regexps = [
	(re.compile(r'Textversion', re.DOTALL), lambda match: ''),
    ]
    remove_tags = [dict(name='hr'),
	dict(name='br'),
	dict(name='small'),
	dict(name='img'),
	dict(name='div', attrs={'class':'textnavi'}),
	dict(name='h1', attrs={'class':'titel'}),
	dict(name='a', attrs={'class':'print'}),
	dict(name='div', attrs={'class':'hline'})]
    feeds = [(u'Politik', u'http://diepresse.com/rss/Politik'),
	(u'Wirtschaft', u'http://diepresse.com/rss/Wirtschaft'),
	(u'Europa', u'http://diepresse.com/rss/EU'),
	(u'Panorama', u'http://diepresse.com/rss/Panorama'),
	(u'Sport', u'http://diepresse.com/rss/Sport'),
	(u'Kultur', u'http://diepresse.com/rss/Kultur'),
	(u'Leben', u'http://diepresse.com/rss/Leben'),
	(u'Tech', u'http://diepresse.com/rss/Tech'),
	(u'Science', u'http://diepresse.com/rss/Science'),
	(u'Bildung', u'http://diepresse.com/rss/Bildung'),
	(u'Gesundheit', u'http://diepresse.com/rss/Gesundheit'),
	(u'Recht', u'http://diepresse.com/rss/Recht'),
	(u'Spectrum', u'http://diepresse.com/rss/Spectrum'),
	(u'Meinung', u'http://diepresse.com/rss/Meinung')]

    def print_version(self, url):
        return url.replace('home','text/home')
