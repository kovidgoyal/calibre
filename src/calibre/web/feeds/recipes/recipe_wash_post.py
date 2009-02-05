import re
from calibre.web.feeds.news import BasicNewsRecipe


class WashingtonPost(BasicNewsRecipe):

    title = 'Washington Post'
    description = 'US political news'
    __author__ = 'Kovid Goyal'
    use_embedded_content   = False
    max_articles_per_feed = 20
    language = _('English')

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
[
    	(r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
    	(r'<div id="apple-rss-sidebar-background">.*?<!-- start Entries -->', lambda match : ''),
    	(r'<!-- end apple-rss-content-area -->.*?</body>', lambda match : '</body>'),
    	(r'<script.*?>.*?</script>', lambda match : ''),
    	(r'<body.*?>.*?.correction {', lambda match : '<body><style>.correction {'),
    	(r'<span class="display:none;" name="pubDate".*?>.*?</body>', lambda match : '<body>'),
    	
    	
    ]
    ]   
     

  
    feeds = [ ('Today\'s Highlights', 'http://www.washingtonpost.com/wp-dyn/rss/linkset/2005/03/24/LI2005032400102.xml'),
     	         ('Politics', 'http://www.washingtonpost.com/wp-dyn/rss/politics/index.xml'),
     	         ('Nation', 'http://www.www.washingtonpost.com/wp-dyn/rss/nation/index.xml'),
     	         ('World', 'http://www.washingtonpost.com/wp-dyn/rss/world/index.xml'),
     	         ('Business', 'http://www.washingtonpost.com/wp-dyn/rss/business/index.xml'),
     	         ('Technology', 'http://www.washingtonpost.com/wp-dyn/rss/technology/index.xml'),
     	         ('Health', 'http://www.washingtonpost.com/wp-dyn/rss/health/index.xml'),
     	         ('Education', 'http://www.washingtonpost.com/wp-dyn/rss/education/index.xml'),
     	         ('Editorials', 'http://www.washingtonpost.com/wp-dyn/rss/linkset/2005/05/30/LI2005053000331.xml'),
     	]



    def print_version(self, url):
        return (url.rpartition('.')[0] + '_pf.html')

