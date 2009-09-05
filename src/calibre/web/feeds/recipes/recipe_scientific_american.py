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
    __author__ = 'Kovid Goyal and Sujata Raman'
    language = 'en'

    oldest_article = 30
    max_articles_per_feed = 100
    no_stylesheets = True
    use_embedded_content   = False
    extra_css = '''
                p{font-weight: normal; font-size:small}
                li{font-weight: normal; font-size:small}
                .headline p{font-size:x-small; font-family:Arial,Helvetica,sans-serif;}
                h2{font-size:x-small;}
                h3{font-size:x-small;font-family:Arial,Helvetica,sans-serif;}
                '''
    remove_tags_before = dict(name='div', attrs={'class':'headline'})

    remove_tags_after  = dict(id=['article'])
    remove_tags        = [
                          dict(id=['sharetools', 'reddit']),
                          dict(name='script'),
                          {'class':['float_left', 'atools']},
                          {"class": re.compile(r'also-in-this')},
                          dict(name='a',title = ["Get the Rest of the Article","Subscribe","Buy this Issue"]),
                          dict(name = 'img',alt = ["Graphic - Get the Rest of the Article"]),
                         ]

    html2lrf_options = ['--base-font-size', '8']
    recursions = 1
    match_regexps = [r'article.cfm.id=\S+page=(2|3|4|5|6|7|8|9|10|11|12|13|14|15)']

    def parse_index(self):
        soup = self.index_to_soup('http://www.scientificamerican.com/sciammag/')
        monthtag = soup.find('div',attrs={'id':'magazine-main_col2'})
        month = self.tag_to_string(monthtag.contents[1])


        self.timefmt = ' [%s]'%(self.tag_to_string(month))
        img = soup.find('img', alt='Scientific American Magazine', src=True)
        if img is not None:
            self.cover_url = img['src']
        features, feeds = [], []
        for p in soup.find(id='magazine-main_col2').findAll('p') :
            a = p.find('a', href=True)

            if a is None: continue
            desc = ''
            s = p.find('span', attrs={'class':"sub"})
            desc = self.tag_to_string(s)

            article = {
                    'url' : a['href'],
                    'title' : self.tag_to_string(a),
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

                if 'article.cfm' in x['href']:
                    article = {
                            'url' : x['href'],
                            'title' : self.tag_to_string(x),
                            'date': '',
                            'description': '',
                        }

                    section.append(article)

        if section:
            feeds.append((title, section))

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
