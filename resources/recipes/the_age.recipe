#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Matthew Briggs <hal.sulphur@gmail.com>'
__docformat__ = 'restructuredtext en'

'''
theage.com.au
'''
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup


class TheAge(BasicNewsRecipe):

    title = 'The Age'
    description = 'Business News, World News and Breaking News in Melbourne, Australia'
    __author__ = 'Matthew Briggs'
    language = 'en_AU'


    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.set_handle_refresh(False)
        return br

    def parse_index(self):

        soup = BeautifulSoup(self.browser.open('http://www.theage.com.au/text/').read())

        feeds, articles = [], []
        feed = None


        for tag in soup.findAll(['h3', 'a']):
            if tag.name == 'h3':
                if articles:
                    feeds.append((feed, articles))
                    articles = []
                feed = self.tag_to_string(tag)
            elif feed is not None and tag.has_key('href') and tag['href'].strip():
                url = tag['href'].strip()
                if url.startswith('/'):
                    url   = 'http://www.theage.com.au' + url
                title = self.tag_to_string(tag)
                articles.append({
                                 'title': title,
                                 'url'  : url,
                                 'date' : strftime('%a, %d %b'),
                                 'description' : '',
                                 'content'     : '',
                                 })

        return feeds



