# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2009, Gerhard Aigner <gerhard.aigner at gmail.com>'

''' http://www.diepresse.at - Austrian Newspaper '''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class DiePresseRecipe(BasicNewsRecipe):
    title = u'diePresse'
    __author__ = 'Gerhard Aigner'
    description = u'DiePresse.com - Die Online-Ausgabe der Österreichischen Tageszeitung Die Presse.' 
    publisher ='DiePresse.com'
    category = 'news, politics, nachrichten, Austria'
    use_embedded_content = False
    remove_empty_feeds = True
    lang = 'de-AT'
    no_stylesheets = True
    encoding = 'ISO-8859-1'
    language = 'de'

    recursions = 0
    oldest_article = 1
    max_articles_per_feed = 100
  
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
  
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
	(u'Wissenschaft', u'http://diepresse.com/rss/Science'),
	(u'Bildung', u'http://diepresse.com/rss/Bildung'),
	(u'Gesundheit', u'http://diepresse.com/rss/Gesundheit'),
	(u'Recht', u'http://diepresse.com/rss/Recht'),
	(u'Spectrum', u'http://diepresse.com/rss/Spectrum'),
	(u'Meinung', u'http://diepresse.com/rss/Meinung')]

    def print_version(self, url):
        return url.replace('home','text/home')

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
	mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
	return soup  