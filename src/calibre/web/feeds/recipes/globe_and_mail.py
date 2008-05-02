#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
globeandmail.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class GlobeAndMail(BasicNewsRecipe):
    
    title = 'Globe and Mail'
    __author__ = 'Kovid Goyal'
    description = 'Canada\'s national newspaper'
    keep_only_tags = [dict(id='content')]
    remove_tags    = [dict(attrs={'class':'nav'}), dict(id=['related', 'TPphoto', 'secondaryNav', 'articleBottomToolsHolder'])]
    
    def parse_index(self):
        src = self.browser.open('http://www.theglobeandmail.com/frontpage/').read()
        soup =  BeautifulSoup(src)
        
        feeds = []
        articles = []
        feed = 'Front Page'
        for tag in soup.findAll(['h3', 'h4']):
            if tag.name == 'h3':
                a = tag.find('a', href=True)
                if a is not None:
                    href = 'http://www.theglobeandmail.com' + a['href'].strip()
                    text = a.find(text=True)
                    if text:
                        text = text.strip()
                        desc = ''
                        summary = tag.findNextSiblings('p', attrs={'class':'summary'}, limit=1)
                        if summary:
                            desc = self.tag_to_string(summary[0], False)
                        articles.append({
                                         'title': text,
                                         'url'  : href,
                                         'desc' : desc,
                                         'date' : '', 
                                         })
            elif tag.name == 'h4':
                if articles:
                    feeds.append((feed, articles))
                articles = []
                feed = self.tag_to_string(tag, False)
                        
        return feeds