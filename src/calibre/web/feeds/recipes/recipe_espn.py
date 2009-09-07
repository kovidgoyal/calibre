#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
espn.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class ESPN(BasicNewsRecipe):

    title       = 'ESPN'
    description = 'Sports news'
    __author__  = 'Kovid Goyal'
    language = 'en'


    needs_subscription = True
    remove_tags = [dict(name='font', attrs={'class':'footer'}), dict(name='hr', noshade='noshade')]
    remove_tags_before = dict(name='font', attrs={'class':'date'})
    center_navbar = False

    feeds = [('Top Headlines', 'http://sports.espn.go.com/espn/rss/news'),
             'http://sports.espn.go.com/espn/rss/nfl/news',
             'http://sports.espn.go.com/espn/rss/nba/news',
             'http://sports.espn.go.com/espn/rss/mlb/news',
             'http://sports.espn.go.com/espn/rss/nhl/news',
             'http://sports.espn.go.com/espn/rss/golf/news',
             'http://sports.espn.go.com/espn/rss/rpm/news',
             'http://sports.espn.go.com/espn/rss/tennis/news',
             'http://sports.espn.go.com/espn/rss/boxing/news',
             'http://soccernet.espn.go.com/rss/news',
             'http://sports.espn.go.com/espn/rss/ncb/news',
             'http://sports.espn.go.com/espn/rss/ncf/news',
             'http://sports.espn.go.com/espn/rss/ncaa/news',
             'http://sports.espn.go.com/espn/rss/outdoors/news',
             'http://sports.espn.go.com/espn/rss/bassmaster/news',
             'http://sports.espn.go.com/espn/rss/oly/news',
             'http://sports.espn.go.com/espn/rss/horse/news']

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.set_handle_refresh(False)
        if self.username is not None and self.password is not None:
            br.open('http://espn.com')
            br.select_form(nr=1)
            br.form.find_control(name='username', type='text').value = self.username
            br.form['password'] = self.password
            br.submit()
        br.set_handle_refresh(True)
        return br

    def print_version(self, url):
        if 'eticket' in url:
            return url.partition('&')[0].replace('story?', 'print?')
        match = re.search(r'story\?(id=\d+)', url)
        if match:
            return 'http://sports.espn.go.com/espn/print?'+match.group(1)+'&type=story'

        return None

    def preprocess_html(self, soup):
        for div in soup.findAll('div'):
            if div.has_key('style') and 'px' in div['style']:
                div['style'] = ''

        return soup

    def postprocess_html(self, soup, first_fetch):
        for div in soup.findAll('div', style=True):
            div['style'] = div['style'].replace('center', 'left')
        return soup

