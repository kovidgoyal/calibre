__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


'''
Fetch Dilbert.
'''
import os

from libprs500.ebooks.lrf.web.profiles import DefaultProfile

class Dilbert(DefaultProfile):

    title = 'Dilbert'
    timefmt = ' [%d %b %Y]'
    max_recursions = 2
    max_articles_per_feed = 6
    html_description = True
    no_stylesheets = True

    def get_feeds(self): 
        return [ ('Dilbert', 'http://feeds.feedburner.com/tapestrydilbert') ]
    
    def get_article_url(self, item):
        return item.find('enclosure')['url']
    
    def build_index(self):
        index = os.path.join(self.temp_dir, 'index.html')
        articles = list(self.parse_feeds(require_url=False).values())[0]
        res = ''
        for item in articles:
            res += '<h3>%s</h3><img style="page-break-after:always" src="%s" />\n'%(item['title'], item['url'])
        res = '<html><body><h1>Dilbert</h1>%s</body></html'%res
        open(index, 'wb').write(res)
        return index
         

