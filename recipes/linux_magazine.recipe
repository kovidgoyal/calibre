#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
linux-magazine.com
'''

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.web.feeds.news import BasicNewsRecipe

class LinuxMagazine(BasicNewsRecipe):
    title                 = u'Linux Magazine'
    __author__            = 'Darko Miletic'
    description           = 'Linux news'  
    language = 'en'
  
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False

    remove_tags_after = dict(name='div', attrs={'class':'end_intro'})
    remove_tags = [
                     dict(name='div' , attrs={'class':'end_intro' })
                    ,dict(name='table'  , attrs={'width':'100%'})
                  ]

    feeds          = [(u'Linux Magazine Full Feed', u'http://www.linux-magazine.com/rss/feed/lmi_full')]
        
    def print_version(self, url):
        raw = self.browser.open(url).read()
        soup = BeautifulSoup(raw.decode('utf8', 'replace'))
        print_link = soup.find('a', {'title':'Print this page'})
        if print_link is None:
            return url
        return 'http://www.linux-magazine.com'+print_link['href']
    
