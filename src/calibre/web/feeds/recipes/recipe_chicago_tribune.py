from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from urlparse import urlparse, urlunparse
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ptempfile import PersistentTemporaryFile
from threading import RLock

class ChicagoTribune(BasicNewsRecipe):
    
    title       = 'Chicago Tribune'
    __author__  = 'Kovid Goyal'
    description = 'Politics, local and business news from Chicago'
    language    = _('English')
    use_embedded_content    = False
    articles_are_obfuscated = True
    remove_tags_before      = dict(name='h1')
    obfuctation_lock        = RLock()
    
    feeds = [
             ('Latest news', 'http://feeds.chicagotribune.com/chicagotribune/news/'),
             ('Local news', 'http://feeds.chicagotribune.com/chicagotribune/news/local/'),
             ('Nation/world', 'http://feeds.chicagotribune.com/chicagotribune/news/nationworld/'),
             ('Hot topics', 'http://feeds.chicagotribune.com/chicagotribune/hottopics/'),
             ('Most E-mailed stories', 'http://feeds.chicagotribune.com/chicagotribune/email/'),
             ('Opinion', 'http://feeds.chicagotribune.com/chicagotribune/opinion/'),
             ('Off Topic', 'http://feeds.chicagotribune.com/chicagotribune/offtopic/'),
             ('Politics', 'http://feeds.chicagotribune.com/chicagotribune/politics/'),
             ('Special Reports', 'http://feeds.chicagotribune.com/chicagotribune/special/'),
             ('Religion News', 'http://feeds.chicagotribune.com/chicagotribune/religion/'),
             ('Business news', 'http://feeds.chicagotribune.com/chicagotribune/business/'),
             ('Jobs and Careers', 'http://feeds.chicagotribune.com/chicagotribune/career/'),
             ('Local scene', 'http://feeds.chicagotribune.com/chicagohomes/localscene/'),
             ('Phil Rosenthal', 'http://feeds.chicagotribune.com/chicagotribune/rosenthal/'),
             ('Tech Buzz', 'http://feeds.chicagotribune.com/chicagotribune/techbuzz/'),
             ('Your Money', 'http://feeds.chicagotribune.com/chicagotribune/yourmoney/'),
             ('Jon Hilkevitch - Getting around', 'http://feeds.chicagotribune.com/chicagotribune/gettingaround/'),
             ('Jon Yates - What\'s your problem?', 'http://feeds.chicagotribune.com/chicagotribune/problem/'),
             ('Garisson Keillor', 'http://feeds.chicagotribune.com/chicagotribune/keillor/'),
             ('Marks Jarvis - On Money', 'http://feeds.chicagotribune.com/chicagotribune/marksjarvisonmoney/'),
             ('Sports', 'http://feeds.chicagotribune.com/chicagotribune/sports/'),
             ('Arts and Architecture', 'http://feeds.chicagotribune.com/chicagotribune/arts/'),
             ('Books', 'http://feeds.chicagotribune.com/chicagotribune/books/'),
             ('Magazine', 'http://feeds.chicagotribune.com/chicagotribune/magazine/'),
             ('Movies', 'http://feeds.chicagotribune.com/chicagotribune/movies/'),
             ('Music', 'http://feeds.chicagotribune.com/chicagotribune/movies/'),
             ('TV', 'http://feeds.chicagotribune.com/chicagotribune/tv/'),
             ('Hypertext', 'http://feeds.chicagotribune.com/chicagotribune/hypertext/'),
             ('iPhone Blog', 'http://feeds.feedburner.com/redeye/iphoneblog'),
             ('Julie\'s Health Club', 'http://feeds.chicagotribune.com/chicagotribune_julieshealthclub/'),
             ]
    
    temp_files = []
    
    def get_article_url(self, article):
        return article.get('feedburner_origlink', article.get('guid', article.get('link')))
    
    def get_obfuscated_article(self, url, logger):
        with self.obfuctation_lock:
            soup = self.index_to_soup(url)
            img = soup.find('img', alt='Print')
            if img is not None:
                a = img.parent.find('a', href=True)
                purl = urlparse(url)
                xurl = urlunparse(purl[:2] + (a['href'], '', '', ''))
                soup = self.index_to_soup(xurl)
                for img in soup.findAll('img', src=True):
                    if img['src'].startswith('/'):
                        img['src'] = urlunparse(purl[:2]+(img['src'], '', '', ''))
                html = unicode(soup)
            else:
                h1 = soup.find(id='page-title')
                body = soup.find(attrs={'class':re.compile('asset-content')})
                html = u'<html><head/><body>%s</body></html>'%(unicode(h1)+unicode(body))
            self.temp_files.append(PersistentTemporaryFile('_chicago_tribune.xhtml'))
            self.temp_files[-1].write(html.encode('utf-8'))
            self.temp_files[-1].close()
            return self.temp_files[-1].name
    
