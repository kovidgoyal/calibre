import re
from libprs500.ebooks.lrf.web.profiles import DefaultProfile


class UnitedPressInternational(DefaultProfile):

    title = 'United Press International'
    max_recursions = 2
    max_articles_per_feed = 15
    html2lrf_options = ['--override-css= "H1 {font-family: Arial; font-weight: bold; color: #000000; size: 10pt;}"']

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
                          [
    	(r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
    	(r'<div id="apple-rss-sidebar-background">.*?<!-- start Entries -->', lambda match : ''),
    	(r'<!-- end apple-rss-content-area -->.*?</body>', lambda match : '</body>'),
    	(r'<script.*?>.*?</script>', lambda match : ''),
    	(r'<body onload=.*?>.*?<a href="http://www.upi.com">', lambda match : '<body style="font: 8pt arial;">'),
    	##(r'<div class=\'headerDIV\'><h2><a style="color: #990000;" href="http://www.upi.com/NewsTrack/Top_News/">Top News</a></h2></div>.*?<br clear="all">', lambda match : ''),
    	(r'<script src="http://www.g.*?>.*?</body>', lambda match : ''),
    	(r'<span style="font: 16pt arial', lambda match : '<span style="font: 12pt arial'),
     ]
    ]   
     

  
    def get_feeds(self):
        return [ ('Top Stories', 'http://www.upi.com/rss/NewsTrack/Top_News/'),
     	         ('Science', 'http://www.upi.com/rss/NewsTrack/Science/'),
     	         ('Heatlth', 'http://www.upi.com/rss/NewsTrack/Health/'),
     	         ('Quirks', 'http://www.upi.com/rss/NewsTrack/Quirks/'),
     	]
    
    def print_version(self, url):
        return (url + 'print_view/')
