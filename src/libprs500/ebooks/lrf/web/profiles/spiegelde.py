__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Spiegel Online.
'''

from libprs500.ebooks.lrf.web.profiles import DefaultProfile

import re

class SpiegelOnline(DefaultProfile): 
    
    title = 'Spiegel Online' 
    timefmt = ' [ %Y-%m-%d %a]'
    max_recursions = 2
    max_articles_per_feed = 40
    use_pubdate = False
    no_stylesheets = True

    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
            [
             # Remove Zum Thema footer
             (r'<div class="spArticleCredit.*?</body>', lambda match: '</body>'),
             ]
            ]
    
    def get_feeds(self): 
        return [ ('Spiegel Online', 'http://www.spiegel.de/schlagzeilen/rss/0,5291,,00.xml') ] 

       
    def print_version(self,url):
        tokens = url.split(',')
        tokens[-2:-2] = ['druck|']
        return ','.join(tokens).replace('|,','-')
