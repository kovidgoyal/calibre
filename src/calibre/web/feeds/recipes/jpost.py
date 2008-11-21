import re
from calibre.web.feeds.news import BasicNewsRecipe

class JerusalemPost(BasicNewsRecipe):

    title = 'Jerusalem Post'
    description = 'News from Israel and the Middle East'
    use_embedded_content   = False
    __author__ = 'Kovid Goyal'
    max_articles_per_feed = 10
    
    
    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
    [
        (r'<HEAD>.*?</HEAD>' , lambda match : '<HEAD></HEAD>'),
        (r'<BODY.*?>.*?<!-- start Entries -->', lambda match : '<BODY><!-- start Entries -->'),
        (r'<!-- end Entries -->.*?</BODY>', lambda match : '</BODY>'),
        (r'<script.*?>.*?</script>', lambda match : ''),
        (r'<div class="apple-rss-article apple-rss-read" onclick=.*?<div class="apple-rss-article-body">', lambda match : ''),
        (r'<img src=\'/images/logo_NWAnews.gif\' alt=\'NWAnews.com :: Northwest Arkansas\' News Source\'.*?>', lambda match : ''),
        (r'<img src=\'/images/logo_adg.gif\'.*?>', lambda match : ''),
        (r'<P CLASS="smallprint">.*?</body>', lambda match : '</body>'),

    ]
    ]
    
    feeds =  [ ('Front Page', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333346'),
                     ('Israel News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1178443463156'),
                     ('Middle East News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333498'),
                     ('International News', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1178443463144'),
                     ('Editorials', 'http://www.jpost.com/servlet/Satellite?pagename=JPost/Page/RSS&cid=1123495333211'),
          ]
          
    def print_version(self, url):
        return ('http://www.jpost.com/servlet/Satellite?cid=' + url.rpartition('&')[2] + '&pagename=JPost%2FJPArticle%2FPrinter')
         
