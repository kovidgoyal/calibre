__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Die Zeit.
'''

from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class ZeitNachrichten(DefaultProfile):
    
    title = 'Die Zeit Nachrichten'
    timefmt = ' [%d %b %Y]'
    max_recursions = 2
    max_articles_per_feed = 40
    html_description = True
    no_stylesheets = True
    encoding = 'latin1'

    
    def get_feeds(self): 
        return [ ('Zeit.de', 'http://newsfeed.zeit.de/news/index') ] 
    
    def print_version(self,url):
        return url.replace('http://www.zeit.de/', 'http://images.zeit.de/text/').replace('?from=rss', '')

