#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
bbc.co.uk
'''

from libprs500.web.feeds.news import BasicNewsRecipe

class BBC(BasicNewsRecipe):
    title          = u'The BBC'
    __author__     = 'Kovid Goyal'
    description    = 'Global news and current affairs from the British Broadcasting Corporation'
    no_stylesheets = True

    remove_tags    = [dict(name='div', attrs={'class':'footer'})]
    extra_css      = '.headline {font-size: x-large;} \n .fact { padding-top: 10pt  }' 

    feeds          = [
                      ('News Front Page', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/front_page/rss.xml'), 
                      ('Science/Nature', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/science/nature/rss.xml'),
                      ('Technology', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/technology/rss.xml'),
                      ('Enterntainment', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/entertainment/rss.xml'),
                      ('Magazine', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/uk_news/magazine/rss.xml'),
                      ('Business', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/business/rss.xml'),
                      ('Health', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/health/rss.xml'),
                      ('Americas', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/americas/rss.xml'),
                      ('Europe', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/europe/rss.xml'),
                      ('South Asia', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/south_asia/rss.xml'),
                      ('UK', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/uk_news/rss.xml'),
                      ('Asia-Pacific', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/asia-pacific/rss.xml'),
                      ('Africa', 'http://newsrss.bbc.co.uk/rss/newsonline_world_edition/africa/rss.xml'),
                    ]

    def print_version(self, url):
        return url.replace('http://', 'http://newsvote.bbc.co.uk/mpapps/pagetools/print/')
