'''
	Profile to download Jutarnji.hr by Valloric
'''

import re
	
from calibre.ebooks.lrf.web.profiles import DefaultProfile 

class USAToday(DefaultProfile):

	title = 'USA Today'
	max_recursions = 2
	timefmt  = ' [%d %b %Y]'
	max_articles_per_feed = 20
	html_description = True
	#no_stylesheets = True

	preprocess_regexps = [
		(re.compile(r'<BODY.*?<!--Article Goes Here-->', re.IGNORECASE | re.DOTALL), lambda match : '<BODY>'),
		(re.compile(r'<!--Article End-->.*?</BODY>', re.IGNORECASE | re.DOTALL), lambda match : '</BODY>'),
		]
	
	## Getting the print version 
	
	def print_version(self, url):
		return 'http://www.printthis.clickability.com/pt/printThis?clickMap=printThis&fb=Y&url=' + url

	
	## Comment out the feeds you don't want retrieved.
	## Or add any new new RSS feed URL's here, sorted alphabetically when converted to LRF
	## If you want one of these at the top, append a space in front of the name.
	
	def get_feeds(self):
		return  [
                (' Top Headlines', 'http://rssfeeds.usatoday.com/usatoday-NewsTopStories'),
                ('Sport Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomSports-TopStories'),
                ('Tech Headlines', 'http://rssfeeds.usatoday.com/usatoday-TechTopStories'),
                ('Travel Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomTravel-TopStories'),
                ('Money Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomMoney-TopStories'),
                ('Entertainment Headlines', 'http://rssfeeds.usatoday.com/usatoday-LifeTopStories'),
                ('Weather Headlines', 'http://rssfeeds.usatoday.com/usatoday-WeatherTopStories'),
		        ('Most Popular', 'http://rssfeeds.usatoday.com/Usatoday-MostViewedArticles'),
                ]