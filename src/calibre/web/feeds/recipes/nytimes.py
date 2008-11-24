#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
mobile.nytimes.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe
from lxml import html

class NYTimesMobile(BasicNewsRecipe):
    
    title       = 'The New York Times (mobile)'
    __author__  = 'Kovid Goyal'
    description = 'Daily news from the New York Times (mobile version)'
    timefmt     = ' [%a, %d %b, %Y]'
    multithreaded_fetch = True
    max_articles_per_feed  = 15
    no_stylesheets = True
    extra_css = '''
    .h1 { font-size: x-large; font-weight: bold; font-family: sans-serif; text-align: left }
    .h2 { font-size: large; font-weight: bold }
    .credit { font-size: small }
    .aut { font-weight: bold }
    .bodycontent { font-family: serif }
    ''' 
    
    remove_tags = [
                   dict(name='div', attrs={'class':['banner center', 'greyBackBlackTop', 'c bB']}), 
                   dict(name='a', href='/main')
                   ]
    remove_tags_after = [
                         dict(name='a', attrs={'name': 'bottom'})
                         ]
    
    def image_url_processor(self, baseurl, url):
        return re.sub(r'(&|&amp;).*', '', url)
    
    def get_browser(self):
        return BasicNewsRecipe.get_browser(mobile_browser=True)
    
    def download(self, for_lrf=False):
        if for_lrf:
            self.max_articles_per_feed = 10
        return BasicNewsRecipe.download(self, for_lrf=for_lrf)
    
    def process_section(self, href):
        raw = self.index_to_soup('http://mobile.nytimes.com/section'+href[href.find('?'):], raw=True)
        articles = []
        while True:
            root = html.fromstring(raw)
            for art in self.find_articles(root):
                append = True
                for x in articles:
                    if x['title'] == art['title']:
                        append = False
                        break
                if append: articles.append(art)
            more = root.xpath('//a[starts-with(@href, "section") and contains(text(), "MORE")]')
            if not more:
                break
            href = more[0].get('href')
            raw = self.index_to_soup('http://mobile.nytimes.com/section'+href[href.find('?'):], raw=True)
        return articles
        
    
    def find_articles(self, root):
        for a in root.xpath('//a[@accesskey]'):
            href = a.get('href')
            yield {
                   'title': a.text.strip(),
                   'date' : '',
                   'url'  : 'http://mobile.nytimes.com/article' + href[href.find('?'):]+'&single=1',
                   'description': '',
                   }
        
    
    def parse_index(self):
        raw = self.index_to_soup('http://mobile.nytimes.com', raw=True)
        root = html.fromstring(raw)
        feeds = [('Latest news', list(self.find_articles(root)))]
            
        for a in root.xpath('//a[starts-with(@href, "section")]'):
            title = a.text.replace('&raquo;', '').replace(u'\xbb', '').strip()
            print 'Processing section:', title
            articles = self.process_section(a.get('href'))
            feeds.append((title, articles))
            
        return feeds
    
    def postprocess_html(self, soup, first_fetch):
        for img in soup.findAll('img', width=True):
            try:
                width = int(img['width'].replace('px', ''))
                if width < 5:
                    img.extract()
                    continue
            except:
                pass
            del img['width']
            del img['height']
            del img.parent['style']
        return soup
