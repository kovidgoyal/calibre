__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Spiegel Online.
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe


class SpeigelOnline(BasicNewsRecipe):
    
    title = 'Spiegel Online' 
    description = 'News from Germany'
    __author__ = 'Kovid Goyal'
    use_embedded_content   = False
    timefmt = ' [ %Y-%m-%d %a]'
    max_articles_per_feed = 40
    no_stylesheets = True

    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
            [
             # Remove Zum Thema footer
             (r'<div class="spArticleCredit.*?</body>', lambda match: '</body>'),
             ]
            ]
    
    feeds= [ ('Spiegel Online', 'http://www.spiegel.de/schlagzeilen/rss/0,5291,,00.xml') ] 

       
    def print_version(self,url):
        tokens = url.split(',')
        tokens[-2:-2] = ['druck|']
        return ','.join(tokens).replace('|,','-')
