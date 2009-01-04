__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch xkcd.
'''

import time
from calibre.web.feeds.news import BasicNewsRecipe

class XkcdCom(BasicNewsRecipe):
    title = 'xkcd'
    description = 'A webcomic of romance and math humor.'
    __author__ = 'Martin Pitt'
    use_embedded_content   = False
    oldest_article = 60
    keep_only_tags = [dict(id='middleContent')]
    remove_tags = [dict(name='ul'), dict(name='h3'), dict(name='br')]
    no_stylesheets = True
    
    def parse_index(self):
        INDEX = 'http://xkcd.com/archive/'

        soup = self.index_to_soup(INDEX) 
        articles = []
        for item in soup.findAll('a', title=True):
            articles.append({
                'date': item['title'],
                'timestamp': time.mktime(time.strptime(item['title'], '%Y-%m-%d'))+1,
                'url': 'http://xkcd.com' + item['href'],
                'title': self.tag_to_string(item).encode('UTF-8'),
                'description': '',
                'content': '',
            })

        return [('xkcd', articles)]
