import re
from calibre.web.feeds.news import BasicNewsRecipe


class AssociatedPress(BasicNewsRecipe):

    title = u'Associated Press'
    description = 'Global news'
    __author__ = 'Kovid Goyal'
    use_embedded_content   = False
    language = 'en'

    max_articles_per_feed = 15
    html2lrf_options = ['--force-page-break-before-tag="chapter"']
    
    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
[
        (r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
        (r'<body class="apple-rss-no-unread-mode" onLoad="setup(null)">.*?<!-- start Entries -->', lambda match : '<body>'),
        (r'<!-- end apple-rss-content-area -->.*?</body>', lambda match : '</body>'),
        (r'<script.*?>.*?</script>', lambda match : ''),
        (r'<body.*?>.*?<span class="headline">', lambda match : '<body><span class="headline"><chapter>'),
        (r'<tr><td><div class="body">.*?<p class="ap-story-p">', lambda match : '<p class="ap-story-p">'),
        (r'<p class="ap-story-p">', lambda match : '<p>'),
        (r'Learn more about our <a href="http://apdigitalnews.com/privacy.html">Privacy Policy</a>.*?</body>', lambda match : '</body>'),
    ]
    ]   
     

  
    feeds = [ ('AP Headlines', 'http://hosted.ap.org/lineups/TOPHEADS-rss_2.0.xml?SITE=ORAST&SECTION=HOME'),
                  ('AP US News', 'http://hosted.ap.org/lineups/USHEADS-rss_2.0.xml?SITE=CAVIC&SECTION=HOME'),
                   ('AP World News', 'http://hosted.ap.org/lineups/WORLDHEADS-rss_2.0.xml?SITE=SCAND&SECTION=HOME'),
                   ('AP Political News', 'http://hosted.ap.org/lineups/POLITICSHEADS-rss_2.0.xml?SITE=ORMED&SECTION=HOME'),
                   ('AP Washington State News', 'http://hosted.ap.org/lineups/WASHINGTONHEADS-rss_2.0.xml?SITE=NYPLA&SECTION=HOME'),
                   ('AP Technology News', 'http://hosted.ap.org/lineups/TECHHEADS-rss_2.0.xml?SITE=CTNHR&SECTION=HOME'),
                   ('AP Health News', 'http://hosted.ap.org/lineups/HEALTHHEADS-rss_2.0.xml?SITE=FLDAY&SECTION=HOME'),
                   ('AP Science News', 'http://hosted.ap.org/lineups/SCIENCEHEADS-rss_2.0.xml?SITE=OHCIN&SECTION=HOME'),
                   ('AP Strange News', 'http://hosted.ap.org/lineups/STRANGEHEADS-rss_2.0.xml?SITE=WCNC&SECTION=HOME'),
        ]