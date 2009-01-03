#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
sciam.com
'''
import re
from lxml import html
from calibre.web.feeds.news import BasicNewsRecipe

class ScientificAmerican(BasicNewsRecipe):
    title = u'Scientific American'
    description = u'Popular science. Monthly magazine.' 
    __author__ = 'Kovid Goyal'
    oldest_article = 30 
    max_articles_per_feed = 100
    no_stylesheets = True
    use_embedded_content   = False
    remove_tags_before = dict(name='div', attrs={'class':'headline'})
    remove_tags_after  = dict(id='article')
    remove_tags        = [
                          dict(id=['sharetools', 'reddit']), 
                          dict(name='script'),
                          {"class": re.compile(r'also-in-this')}
                         ]
    html2lrf_options = ['--base-font-size', '8']
    recursions = 1
    match_regexps = [r'article.cfm.id=\S+page=(2|3|4|5|6|7|8|9|10|11|12|13|14)']
#    feeds = [
#             (u'Latest News', u'http://rss.sciam.com/ScientificAmerican-News'), 
#             (u'Global', u'http://rss.sciam.com/ScientificAmerican-Global'), 
#             (u'Health', u'http://rss.sciam.com/sciam/health'), 
#             (u'Space', u'http://rss.sciam.com/sciam/space'), 
#             (u'Technology', u'http://rss.sciam.com/sciam/technology'), 
#             (u'Biology', u'http://rss.sciam.com/sciam/biology'), 
#             (u'Mind & Brain', u'http://rss.sciam.com/sciam/mind-and-brain'), 
#             (u"What's Next", u'http://rss.sciam.com/sciam/whats-next'), 
#             (u'Archeology and Paleontology', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=archaeology-and-paleontology'), 
#             (u'Physics', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=physics'), 
#             (u'Math', u'http://rss.sciam.com/sciam/math'), 
#             (u'History of Science', u'http://www.sciam.com/page.cfm?section=rsscategory&alias=history-of-science'), 
#             (u'Chemistry', u'http://rss.sciam.com/sciam/chemistry'), 
#             (u'Mind Matters', u'http://rss.sciam.com/ScientificAmerican-MindBlog')
#            ]
#    
    def parse_index(self):
        src = self.browser.open('http://www.sciam.com/sciammag/').read()
        root = html.fromstring(src)
        self.cover_url = root.xpath('//img[re:match(@src, "cover_")]', 
                                    namespaces={'re':'http://exslt.org/regular-expressions'}
                                    )[0].get('src')
        self.timefmt = ' [%s]'%(root.xpath('//div[@id = "magazine-month"]')[0].text)
        feeds = []
        features = []
        for a in root.xpath('//a[@href and @title = "Feature"]'):
            if not a.text.strip():
                continue
            article = {
                       'url'    : a.get('href'),
                       'title'  : u''.join(a.xpath('./text()')),
                       'date'   : '',
                       'description' : '',   
                       }
            for s in a.itersiblings('span'):
                if s.get('class', '') == 'sub':
                    article['description'] += u''.join(s.xpath('./text()')) + ' '
            features.append(article)
        if features:
            feeds.append(('Features', features))
            
        departments = []
        for a in root.xpath('//a[@href and @class="title"]'):
            txt = u''.join(a.xpath('./text()')).strip()
            if not txt:
                continue
            article = {
                       'url'    : a.get('href'),
                       'title'  : txt,
                       'date'   : '',
                       'description' : '',   
                       }
            p = a.getparent()
            p.remove(a)
            article['description'] = u''.join(p.xpath('./text()'))
            departments.append(article)
            
        feeds.append(('Departments', departments))
        opinion = []
        for a in root.xpath('//div[@id = "opinion"]//a[@href]'):
            txt = u''.join(a.xpath('./text()')).strip()
            if not txt:
                continue
            article = {
                       'url'    : a.get('href'),
                       'title'  : txt,
                       'date'   : '',
                       'description' : '',   
                       }
            opinion.append(article)
        feeds.append(('Opinion', opinion))
        
        ontheweb = []
        for a in root.xpath('//div[@id = "ontheweb"]//a[@href]'):
            txt = u''.join(a.xpath('./text()')).strip()
            if not txt:
                continue
            article = {
                       'url'    : a.get('href'),
                       'title'  : txt,
                       'date'   : '',
                       'description' : '',   
                       }
            ontheweb.append(article)
        feeds.append(('On the web', ontheweb))
        
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
