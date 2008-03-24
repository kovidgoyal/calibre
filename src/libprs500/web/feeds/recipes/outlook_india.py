#!/usr/bin/env  python

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
outlookindia.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe
import re

class OutlookIndia(BasicNewsRecipe):
    
    title = 'Outlook India'
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

    def postprocess_html(self, soup):
        bad = []
        for table in soup.findAll('table'):
            if table.find(text=re.compile(r'\(\d+ of \d+\)')):
                bad.append(table)
        for b in bad:
            b.extract()
        return soup
    