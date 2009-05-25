#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
sciam.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class ScientificAmerican(BasicNewsRecipe):
    title = u'Scientific American'
    description = u'Popular science. Monthly magazine.'
    __author__ = 'Kovid Goyal'
    language = _('English')
    oldest_article = 30
    max_articles_per_feed = 100
    no_stylesheets = True
    use_embedded_content   = False
    remove_tags_before = dict(name='div', attrs={'class':'headline'})
    remove_tags_after  = dict(id=['article'])
    remove_tags        = [
                          dict(id=['sharetools', 'reddit']),
                          dict(name='script'),
                          {'class':['float_left', 'atools']},
                          {"class": re.compile(r'also-in-this')}
                         ]
    html2lrf_options = ['--base-font-size', '8']
    recursions = 1
    match_regexps = [r'article.cfm.id=\S+page=(2|3|4|5|6|7|8|9|10|11|12|13|14|15)']

    def parse_index(self):
        soup = self.index_to_soup('http://www.scientificamerican.com/sciammag/')
        month = soup.find(id='magazine-month')
        self.timefmt = ' [%s]'%(self.tag_to_string(month))
        img = soup.find('img', alt='Scientific American Magazine', src=True)
        if img is not None:
            self.cover_url = img['src']
        features, feeds = [], []
        for p in soup.find(id='magazine-info').findAll('p') + \
                soup.find(id='magazine-info-more').findAll('p'):
            all_as = p.findAll('a', href=True)
            a = all_as[0]
            if a is None: continue
            desc = ''
            for s in p.find('span', attrs={'class':'sub'}):
                desc += self.tag_to_string(s)

            article = {
                    'url' : a.get('href'),
                    'title' : self.tag_to_string(all_as[-1]),
                    'date' : '',
                    'description' : desc,
                    }
            features.append(article)
        feeds.append(('Features', features))

        section = []
        found = []
        title = None
        for x in soup.find(id='magazine-main_col1').findAll(['div', 'a']):
            if x.name == 'div':
                if section:
                    feeds.append((title, section))
                title = self.tag_to_string(x)
                section = []
            else:
                if title is None or not a.get('href', False) or a.get('href', None) in found:
                    continue
                article = {
                        'url' : x['href'],
                        'title' : self.tag_to_string(x),
                        'date': '',
                        'description': '',
                        }
                section.append(article)
        if section:
            feeds.append((title, section))

        articles = []
        for a in soup.find(id='opinion').findAll('a', href=True):
            articles.append({'url':a['href'], 'title':self.tag_to_string(a),
                'description':'', 'date':''})
        feeds.append(('Opinion', articles))

        return feeds


    def postprocess_html(self, soup, first_fetch):
        if soup is not None:
            for span in soup.findAll('span', attrs={'class':'pagination'}):
                span.extract()
            if not first_fetch:
                div = soup.find('div', attrs={'class':'headline'})
                if div:
                    div.extract()
        return soup
