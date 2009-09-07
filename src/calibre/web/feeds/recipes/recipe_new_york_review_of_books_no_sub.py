#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
nybooks.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
from lxml import html
from calibre.constants import preferred_encoding

class NewYorkReviewOfBooks(BasicNewsRecipe):
    
    title = u'New York Review of Books (no subscription)'
    description = u'Book reviews'
    language = 'en'

    __author__ = 'Kovid Goyal' 
    remove_tags_before = {'id':'container'}
    remove_tags = [{'class':['noprint', 'ad', 'footer']}, {'id':'right-content'}]

    def parse_index(self):
        root = html.fromstring(self.browser.open('http://www.nybooks.com/current-issue').read())
        date = root.xpath('//h4[@class = "date"]')[0]
        self.timefmt = ' ['+date.text.encode(preferred_encoding)+']'
        articles = []
        for tag in date.itersiblings():
            if tag.tag == 'h4': break
            if tag.tag == 'p':
                if tag.get('class') == 'indented':
                    articles[-1]['description'] += html.tostring(tag)
                else:
                    href = tag.xpath('descendant::a[@href]')[0].get('href')
                    article = {
                               'title': u''.join(tag.xpath('descendant::text()')),
                               'date' : '',
                               'url'  : 'http://www.nybooks.com'+href,
                               'description': '',
                               }
                    articles.append(article)
                    
        return [('Current Issue', articles)]
       
