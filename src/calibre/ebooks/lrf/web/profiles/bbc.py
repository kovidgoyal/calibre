__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Fetch the BBC.
'''
import re

from calibre.ebooks.lrf.web.profiles import DefaultProfile
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class BBC(DefaultProfile):
    
    title = 'The BBC'
    max_recursions = 2
    timefmt  = ' [%a, %d %b, %Y]'
    no_stylesheets = True
    
    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
              [
               # Remove footer from individual stories
               (r'<div class=.footer.>.*?Published', 
                lambda match : '<p></p><div class="footer">Published'),
               # Add some style info in place of disabled stylesheet
               (r'<link.*?type=.text/css.*?>', lambda match :
                '''<style type="text/css">
                    .headline {font-size: x-large;}
                    .fact { padding-top: 10pt  }
                    </style>'''),
               ]
                  ]
    
        
    def print_version(self, url):
        return url.replace('http://', 'http://newsvote.bbc.co.uk/mpapps/pagetools/print/')
    
    def get_feeds(self):
        src = self.browser.open('http://news.bbc.co.uk/1/hi/help/3223484.stm').read()
        soup = BeautifulSoup(src[src.index('<html'):])
        feeds = []
        ul =  soup.find('ul', attrs={'class':'rss'})
        for link in ul.findAll('a'):
            feeds.append((link.string, link['href']))
        return feeds

