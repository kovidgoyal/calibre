import re

from calibre.web.feeds.news import BasicNewsRecipe


class Reuters(BasicNewsRecipe):

    title = 'Reuters'
    description = 'Global news'
    __author__ = 'Kovid Goyal'
    use_embedded_content   = False
    language = 'en'

    max_articles_per_feed = 10

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
[
        ##(r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
        (r'<div id="apple-rss-sidebar-background">.*?<!-- start Entries -->', lambda match : ''),
        (r'<!-- end apple-rss-content-area -->.*?</body>', lambda match : '</body>'),
        (r'<script.*?>.*?</script>', lambda match : ''),
        (r'<body>.*?<div class="contentBand">', lambda match : '<body>'),
        (r'<h3>Share:</h3>.*?</body>', lambda match : '<!-- END:: Shared Module id=36615 --></body>'),
        (r'<div id="atools" class="articleTools">.*?<div class="linebreak">', lambda match : '<div class="linebreak">'),
    ]
    ]   
     

  
    feeds = [ ('Top Stories', 'http://feeds.reuters.com/reuters/topNews?format=xml'),
                  ('US News', 'http://feeds.reuters.com/reuters/domesticNews?format=xml'),
                  ('World News', 'http://feeds.reuters.com/reuters/worldNews?format=xml'),
                  ('Politics News', 'http://feeds.reuters.com/reuters/politicsNews?format=xml'),
                  ('Science News', 'http://feeds.reuters.com/reuters/scienceNews?format=xml'),
                  ('Environment News', 'http://feeds.reuters.com/reuters/Environment?format=xml'),
                  ('Technology News', 'http://feeds.reuters.com/reuters/technologyNews?format=xml'),
                  ('Oddly Enough News', 'http://feeds.reuters.com/reuters/oddlyEnoughNews?format=xml')
         ]
         
    def print_version(self, url):
        return ('http://www.reuters.com/article/id' + url + '?sp=true')
