'''
	Profile to download Jutarnji.hr
'''

import re
	
from libprs500.ebooks.lrf.web.profiles import DefaultProfile 

class NewYorker(DefaultProfile):
	
	title = 'The New Yorker'
	max_recursions = 2
	timefmt  = ' [%d %b %Y]'
	max_articles_per_feed = 20
	html_description = True
	no_stylesheets = True
	oldest_article = 14
	
	
	## Getting the print version 
	def print_version(self, url):
		return url + '?printable=true'


	preprocess_regexps = [
		(re.compile(r'<body.*?<!-- start article content -->', re.IGNORECASE | re.DOTALL), lambda match : '<body>'),
		(re.compile(r'<div class="utils"'), 
		 lambda match : '<div class="utils" style="display:none"'),
		(re.compile(r'<div class="articleRailLinks"'), 
		 lambda match : '<div class="articleRailLinks" style="display:none"'),
		(re.compile(r'<div id="keywords"'), 
		 lambda match : '<div id="keywords" style="display:none"'), 
		(re.compile(r'<!-- end article body -->.*?</body>', re.IGNORECASE | re.DOTALL), lambda match : '</body>'), 
		(re.compile(r'<!-- start video content -->.*?<!-- end video content -->', re.IGNORECASE | re.DOTALL), lambda match : '<!-- start video content --><!-- end video content -->'), 
		]
	
		
	## Comment out the feeds you don't want retrieved.
	## Or add any new new RSS feed URL's here, sorted alphabetically when converted to LRF
	## If you want one of these at the top, append a space in front of the name.
	
	def get_feeds(self):
		return  [
        ('Online Only', 'http://feeds.newyorker.com/services/rss/feeds/online.xml'), 
        ('The Talk Of The Town', 'http://feeds.newyorker.com/services/rss/feeds/talk.xml'), 
		('Reporting and Essays', 'http://feeds.newyorker.com/services/rss/feeds/reporting.xml'), 
        ('Arts and Culture', 'http://feeds.newyorker.com/services/rss/feeds/arts.xml'), 
        ('Humor', 'http://feeds.newyorker.com/services/rss/feeds/humor.xml'), 
        ('Fiction and Poetry', 'http://feeds.newyorker.com/services/rss/feeds/fiction.xml'), 
		('Comment', 'http://feeds.newyorker.com/services/rss/feeds/comment.xml'), 
		('The Financial Page', 'http://feeds.newyorker.com/services/rss/feeds/financial.xml'), 
		('Politics', 'http://feeds.newyorker.com/services/rss/feeds/politics.xml'), 
		('Movies', 'http://feeds.newyorker.com/services/rss/feeds/movies.xml'), 
		('Books', 'http://feeds.newyorker.com/services/rss/feeds/books.xml'), 
		('Tables For Two', 'http://feeds.newyorker.com/services/rss/feeds/tables.xml'), 
                ]