import re
from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class ChristianScienceMonitor(DefaultProfile):

    title = 'Christian Science Monitor'
    max_recursions = 2
    max_articles_per_feed = 20
    use_pubdate = False
    html_description = True
    html2lrf_options = ['--ignore-tables', '--base-font-size=8.0', '--wordspace=2.0',]

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
[
        (r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
        (r'<body class="apple-rss-no-unread-mode" onLoad="setup(null)">.*?<!-- start Entries -->', lambda match : '<BODY><!-- start Entries -->'),
        (r'<!-- end Entries -->.*?</BODY>', lambda match : '<!-- end Entries --></BODY>'),
        (r'<script>.*?</script>', lambda match : ''),
        (r'<body>.*?<div class="portlet-container">', lambda match : '<body><div class="portlet-container">'),
        (r'<div class="pubdate">.*?</div>', lambda match : ''),
        (r'<div class="factbox">.*?</body>', lambda match : '</body>'),

    ]
    ]
     

  
    def get_feeds(self):
        return [ ('Top News', 'http://rss.csmonitor.com/feeds/top'),
                  ('Terrorism', 'http://rss.csmonitor.com/terrorismSecurity'),
                  ('World', 'http://rss.csmonitor.com/feeds/world'),
               ] 
          
          
    def print_version(self, url):
        resolved_url = self.browser.open(url).geturl()
        return resolved_url.strip()[:-1]  