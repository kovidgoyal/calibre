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
import re
from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class Atlantic(DefaultProfile):
    
    title = 'The Atlantic'
    max_recursions = 2
    INDEX = 'http://www.theatlantic.com/doc/current'
    
    preprocess_regexps = [
                          (re.compile(r'<body.*?<div id="storytop"', re.DOTALL|re.IGNORECASE), 
                           lambda m: '<body><div id="storytop"')
                          ]
    
    def parse_feeds(self):
        articles = []
        
        src = self.browser.open(self.INDEX).read()
        soup = BeautifulSoup(src)
        
        issue = soup.find('span', attrs={'class':'issue'})
        if issue:
            self.timefmt = ' [%s]'%self.tag_to_string(issue).rpartition('|')[-1].strip().replace('/', '-')
        
        for item in soup.findAll('div', attrs={'class':'item'}):
            a = item.find('a')
            if a and a.has_key('href'):
                url = a['href']
                url = 'http://www.theatlantic.com/'+url.replace('/doc', 'doc/print')
                title = self.tag_to_string(a)
                byline = item.find(attrs={'class':'byline'})
                date = self.tag_to_string(byline) if byline else ''
                description = ''
                articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':description
                                })
                
        
        return {'Current Issue' : articles }
        
        