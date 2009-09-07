__license__   = 'GPL v3'
__copyright__ = '2008, Derry FitzGerald. 2009 Modified by Ray Kinsella'
'''
irishtimes.com
'''
import re

from calibre.web.feeds.news import BasicNewsRecipe

class IrishTimes(BasicNewsRecipe):
    title          = u'The Irish Times'
    __author__     = 'Derry FitzGerald and Ray Kinsella'
    language = 'en'

    no_stylesheets = True
    simultaneous_downloads= 1
	
    r 			   = re.compile('.*(?P<url>http:\/\/www.irishtimes.com\/.*\.html).*')
    remove_tags    = [dict(name='div', attrs={'class':'footer'})]
    extra_css      = '.headline {font-size: x-large;} \n .fact { padding-top: 10pt  }' 

    feeds          = [
                      ('Frontpage', 'http://www.irishtimes.com/feeds/rss/newspaper/index.rss'), 
                      ('Ireland', 'http://www.irishtimes.com/feeds/rss/newspaper/ireland.rss'),
                      ('World', 'http://www.irishtimes.com/feeds/rss/newspaper/world.rss'),
                      ('Finance', 'http://www.irishtimes.com/feeds/rss/newspaper/finance.rss'),
                      ('Features', 'http://www.irishtimes.com/feeds/rss/newspaper/features.rss'),
                      ('Sport', 'http://www.irishtimes.com/feeds/rss/newspaper/sport.rss'),
                      ('Opinion', 'http://www.irishtimes.com/feeds/rss/newspaper/opinion.rss'),
                      ('Letters', 'http://www.irishtimes.com/feeds/rss/newspaper/letters.rss'),
                    ]
	

    def print_version(self, url):
        return url.replace('.html', '_pf.html')
		
    def get_article_url(self, article):
        m = self.r.match(article.get('description',  None))
        print m.group('url')
        return m.group('url')