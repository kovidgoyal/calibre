__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Profile to download FAZ.net
'''
import re

from calibre.ebooks.lrf.web.profiles import DefaultProfile 

class FazNet(DefaultProfile): 

    title = 'FAZ NET' 
    max_recursions = 2 
    html_description = True 
    max_articles_per_feed = 30 

    preprocess_regexps = [
       (re.compile(r'Zum Thema</span>.*?</BODY>', re.IGNORECASE | re.DOTALL), 
        lambda match : ''),
    ]    


    def get_feeds(self): 
        return [ ('FAZ.NET', 'http://www.faz.net/s/Rub/Tpl~Epartner~SRss_.xml') ] 

    def print_version(self, url): 
        return url.replace('.html?rss_aktuell', '~Afor~Eprint.html') 

