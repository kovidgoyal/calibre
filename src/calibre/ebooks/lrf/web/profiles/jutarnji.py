'''
	Profile to download Jutarnji.hr by Valloric
'''

import re
	
from calibre.ebooks.lrf.web.profiles import DefaultProfile 

class Jutarnji(DefaultProfile):

	title = 'Jutarnji'
	max_recursions = 2
	timefmt  = ' [%d %b %Y]'
	max_articles_per_feed = 80
	html_description = True
	no_stylesheets = True

	preprocess_regexps = [
		(re.compile(r'<body.*?<span class="vijestnaslov">', re.IGNORECASE | re.DOTALL), lambda match : '<body><span class="vijestnaslov">'), 
		(re.compile(r'</div>.*?</td>', re.IGNORECASE | re.DOTALL), lambda match : '</div></td>'), 
   		(re.compile(r'<a name="addComment.*?</body>', re.IGNORECASE | re.DOTALL), lambda match : '</body>'), 
		(re.compile(r'<br>', re.IGNORECASE | re.DOTALL), lambda match : ''), 
		]
	
	## Getting the print version 
	
	def print_version(self, url):
		return 'http://www.jutarnji.hr/ispis_clanka.jl?artid=' + url[len(url)-9:len(url)-3]

	
	## Comment out the feeds you don't want retrieved.
	## Or add any new new RSS feed URL's here, sorted alphabetically when converted to LRF
	## If you want one of these at the top, append a space in front of the name.
	
	def get_feeds(self):
		return  [
                (' Naslovnica', 'http://www.jutarnji.hr/rss'), 
                ('Sport', 'http://www.jutarnji.hr/sport/rss'), 
                ('Novac', 'http://www.jutarnji.hr/novac/rss'), 
                ('Kultura i zivot', 'http://www.jutarnji.hr/kultura_i_zivot/rss'), 
                ('Automoto', 'http://www.jutarnji.hr/auto_moto/rss'), 
                ('Hi-Tech', 'http://www.jutarnji.hr/kultura_i_zivot/hi-tech/rss'), 
                ('Dom i nekretnine', 'http://www.jutarnji.hr/nekretnine/rss'), 
                ]