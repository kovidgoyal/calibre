__license__   = 'GPL v3'
__copyright__ = '2008, Derry FitzGerald'
'''
irishtimes.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class IrishTimes(BasicNewsRecipe):
    title          = u'The Irish Times'
    __author__     = 'Derry FitzGerald'
    no_stylesheets = True

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
                      ('Health', 'http://www.irishtimes.com/feeds/rss/newspaper/health.rss'),
                      ('Education and Parenting', 'http://www.irishtimes.com/feeds/rss/newspaper/education.rss'),
                      ('Science Today', 'http://www.irishtimes.com/feeds/rss/newspaper/sciencetoday.rss'),
                      ('The Ticket', 'http://www.irishtimes.com/feeds/rss/newspaper/theticket.rss'),
                      ('Weekend', 'http://www.irishtimes.com/feeds/rss/newspaper/weekend.rss'),
                      ('News Features', 'http://www.irishtimes.com/feeds/rss/newspaper/newsfeatures.rss'),
                      ('Magazine', 'http://www.irishtimes.com/feeds/rss/newspaper/magazine.rss'),
                    ]

    def print_version(self, url):
        return url.replace('.html', '_pf.html')