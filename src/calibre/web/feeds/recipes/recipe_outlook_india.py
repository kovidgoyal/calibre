#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
outlookindia.com
'''

from calibre.web.feeds.news import BasicNewsRecipe
import re

class OutlookIndia(BasicNewsRecipe):
    
    title = 'Outlook India'
    __author__  = 'Kovid Goyal'
    description = 'Weekly news magazine focussed on India.'
    recursions = 1
    match_regexp = r'full.asp.*&pn=\d+'
    html2lrf_options = ['--ignore-tables']
    
    remove_tags = [
                   dict(name='img', src="images/space.gif"),
                   dict(name=lambda tag: tag.name == 'tr' and tag.find('img', src="image/tl.gif") is not None ),
                   dict(name=lambda tag: tag.name == 'table' and tag.find('font', attrs={'class':'fontemailfeed'}) is not None),
                   ]
    
    preprocess_regexps = [
                          (re.compile(r'<body.*?<!--Add Banner ends from here-->', re.DOTALL|re.IGNORECASE),
                           lambda match: '<body>'),
                          
                          (re.compile(r'>More Stories:.*', re.DOTALL), 
                           lambda match: '></body></html>'),
                          
                          (re.compile(r'<!-- Google panel start -->.*', re.DOTALL),
                           lambda match: '</body></html>'), 
                          ]
    
    def parse_index(self):
        soup = self.index_to_soup('http://www.outlookindia.com/archivecontents.asp')
        feeds = []
        title = None
        bogus = True
        for table in soup.findAll('table'):
            if title is None:
                td = table.find('td', background="images/content_band1.jpg")
                if td is not None:
                    title = self.tag_to_string(td, False)
                    title = title.replace(u'\xa0', u'').strip()
                    if 'Cover Story' in title and bogus:
                        bogus = False
                        title = None
            else:
                articles = []
                for a in table.findAll('a', href=True):
                    if a.find('img') is not None:
                        continue
                    atitle = self.tag_to_string(a, use_alt=False)
                    desc = a.findNextSibling('font', attrs={'class':'fontintro'})
                    if desc is not None:
                        desc = self.tag_to_string(desc)
                    if not desc:
                        desc = ''
                    articles.append({
                            'title':atitle,
                            'description': desc,
                            'content': '',
                            'url':'http://www.outlookindia.com/'+a['href'],
                            'date': '',
                                     })
                feeds.append((title, articles))
                title = None 
                
                    
        return feeds

    def postprocess_html(self, soup, first_fetch):
        bad = []
        for table in soup.findAll('table'):
            if table.find(text=re.compile(r'\(\d+ of \d+\)')):
                bad.append(table)
        for b in bad:
            b.extract()
        return soup
    
