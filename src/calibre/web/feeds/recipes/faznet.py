__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Profile to download FAZ.net
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
 

class FazNet(BasicNewsRecipe): 

    title = 'FAZ NET'
    __author__ = 'Kovid Goyal'
    description = 'News from Germany'
    use_embedded_content   = False 
    max_articles_per_feed = 30 

    preprocess_regexps = [
       (re.compile(r'Zum Thema</span>.*?</BODY>', re.IGNORECASE | re.DOTALL), 
        lambda match : ''),
    ]    


    feeds = [ ('FAZ.NET', 'http://www.faz.net/s/Rub/Tpl~Epartner~SRss_.xml') ] 

    def print_version(self, url): 
        return url.replace('.html?rss_aktuell', '~Afor~Eprint.html') 

