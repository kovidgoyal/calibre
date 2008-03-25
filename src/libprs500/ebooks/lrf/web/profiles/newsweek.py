__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Profile to download Newsweek
'''
from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class Newsweek(DefaultProfile):
    
    title = 'Newsweek'
    max_recursions = 2
    timefmt  = ' [%d %b %Y]'
    html_description = True
    oldest_article        = 15
    
        
    def print_version(self, url):
        if not url.endswith('/'):
            url += '/'
        return url + 'output/print'
    
    def get_feeds(self):
        return [
             ('Top News', 'http://feeds.newsweek.com/newsweek/TopNews',),
             ('Periscope', 'http://feeds.newsweek.com/newsweek/periscope'),
             ('Politics', 'http://feeds.newsweek.com/headlines/politics'),
             ('Health', 'http://feeds.newsweek.com/headlines/health'),
             ('Business', 'http://feeds.newsweek.com/headlines/business'),
             ('Science and Technology', 'http://feeds.newsweek.com/headlines/technology/science'),
             ('National News', 'http://feeds.newsweek.com/newsweek/NationalNews'),
             ('World News', 'http://feeds.newsweek.com/newsweek/WorldNews'),
             ('Iraq', 'http://feeds.newsweek.com/newsweek/iraq'),
             ('Society', 'http://feeds.newsweek.com/newsweek/society'),
             ('Entertainment', 'http://feeds.newsweek.com/newsweek/entertainment'),
             ]
        
        