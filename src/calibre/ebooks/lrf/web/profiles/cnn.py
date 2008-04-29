__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Profile to download CNN
'''
import re
from calibre.ebooks.lrf.web.profiles import DefaultProfile

class CNN(DefaultProfile):
    
    title = 'CNN'
    max_recursions = 2
    timefmt  = ' [%d %b %Y]'
    html_description = True
    no_stylesheets = True
    oldest_article        = 15

    preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in [
        (r'<head>.*?<title', lambda match : '<head><title'),
        (r'</title>.*?</head>', lambda match : '</title></head>'),
        (r'<body.*?<\!\-\-Article.*?>', lambda match : ''),
        (r'<\!\-\-Article End\-\->.*?</body>', lambda match : '</body>'),
        (r'(</h\d>)<ul>.*?</ul>', lambda match : match.group(1)), # drop story highlights
        (r'<h2>(.*?)</h2><h1>(.*?)</h1>', lambda match : '<h1>' + match.group(1) + '</h1><h2>' + match.group(2) + '</h2>'), # sports uses h2 for main title and h1 for subtitle (???) switch these around
        (r'<span class="cnnEmbeddedMosLnk">.*?</span>', lambda match : ''), # drop 'watch more' links
        (r'(<div class="cnnstorybody">).*?(<p)', lambda match : match.group(1) + match.group(2)), # drop sports photos
        (r'</?table.*?>|</?tr.*?>|</?td.*?>', lambda match : ''), # drop table formatting
        (r'<div class="cnnendofstorycontent".*?>.*?</div>', lambda match : ''), # drop extra business links
        (r'<a href="#TOP">.*?</a>', lambda match : '') # drop business 'to top' link
        ] ]

    def print_version(self, url):
        return 'http://www.printthis.clickability.com/pt/printThis?clickMap=printThis&fb=Y&url=' + url
    
    def get_feeds(self):
        return [
             ('Top News', 'http://rss.cnn.com/rss/cnn_topstories.rss'),
             ('World', 'http://rss.cnn.com/rss/cnn_world.rss'),
             ('U.S.', 'http://rss.cnn.com/rss/cnn_us.rss'),
             ('Sports', 'http://rss.cnn.com/rss/si_topstories.rss'),
             ('Business', 'http://rss.cnn.com/rss/money_latest.rss'),
             ('Politics', 'http://rss.cnn.com/rss/cnn_allpolitics.rss'),
             ('Law', 'http://rss.cnn.com/rss/cnn_law.rss'),
             ('Technology', 'http://rss.cnn.com/rss/cnn_tech.rss'),
             ('Science & Space', 'http://rss.cnn.com/rss/cnn_space.rss'),
             ('Health', 'http://rss.cnn.com/rss/cnn_health.rss'),
             ('Entertainment', 'http://rss.cnn.com/rss/cnn_showbiz.rss'),
             ('Education', 'http://rss.cnn.com/rss/cnn_education.rss'),
             ('Offbeat', 'http://rss.cnn.com/rss/cnn_offbeat.rss'),
             ('Most Popular', 'http://rss.cnn.com/rss/cnn_mostpopular.rss')
             ]
