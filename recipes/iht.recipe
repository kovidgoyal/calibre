__license__   = 'GPL v3'
__copyright__ = '2008, Derry FitzGerald'
'''
iht.com
'''
import re

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ptempfile import PersistentTemporaryFile


class InternationalHeraldTribune(BasicNewsRecipe):
    title          = u'The International Herald Tribune'
    __author__     = 'Derry FitzGerald'
    language = 'en'

    oldest_article = 1
    max_articles_per_feed = 10
    no_stylesheets = True

    remove_tags    = [dict(name='div', attrs={'class':'footer'}),
                      dict(name=['form'])]
    preprocess_regexps = [
            (re.compile(r'<!-- webtrends.*', re.DOTALL),
             lambda m:'</body></html>')
                          ]
    extra_css      = '.headline {font-size: x-large;} \n .fact { padding-top: 10pt  }'

    feeds          = [
                      (u'Frontpage', u'http://www.iht.com/rss/frontpage.xml'),
                      (u'Business', u'http://www.iht.com/rss/business.xml'),
                      (u'Americas', u'http://www.iht.com/rss/america.xml'),
                      (u'Europe', u'http://www.iht.com/rss/europe.xml'),
                      (u'Asia', u'http://www.iht.com/rss/asia.xml'),
                      (u'Africa and Middle East', u'http://www.iht.com/rss/africa.xml'),
                      (u'Opinion', u'http://www.iht.com/rss/opinion.xml'),
                      (u'Technology', u'http://www.iht.com/rss/technology.xml'),
                      (u'Health and Science', u'http://www.iht.com/rss/healthscience.xml'),
                      (u'Sports', u'http://www.iht.com/rss/sports.xml'),
                      (u'Culture', u'http://www.iht.com/rss/arts.xml'),
                      (u'Style and Design', u'http://www.iht.com/rss/style.xml'),
                      (u'Travel', u'http://www.iht.com/rss/travel.xml'),
                      (u'At Home Abroad', u'http://www.iht.com/rss/athome.xml'),
                      (u'Your Money', u'http://www.iht.com/rss/yourmoney.xml'),
                      (u'Properties', u'http://www.iht.com/rss/properties.xml')
                    ]
    temp_files = []
    articles_are_obfuscated = True

    def get_obfuscated_article(self, url, logger):
        br = self.get_browser()
        br.open(url)
        br.select_form(name='printFriendly')
        res = br.submit()
        html = res.read()
        self.temp_files.append(PersistentTemporaryFile('_iht.html'))
        self.temp_files[-1].write(html)
        self.temp_files[-1].close()
        return self.temp_files[-1].name
