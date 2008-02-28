##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
Profile to download the New York Times
'''
import re, time

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class NYTimes(DefaultProfile):
    
    title   = 'The New York Times'
    timefmt = ' [%a, %d %b, %Y]'
    needs_subscription = True
    max_recursions = 2
    recommended_frequency = 1
    encoding = 'cp1252'
    html2lrf_options = ['--base-font-size=0']
    
    
    preprocess_regexps = \
            [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
              [
               # Remove header bar
               (r'(<body.*?>).*?<h1', lambda match: match.group(1)+'<h1'),
               (r'<div class="articleTools">.*></ul>', lambda match : ''),
               # Remove footer bar
               (r'<\!--  end \#article -->.*', lambda match : '</body></html>'),
               (r'<div id="footer">.*', lambda match : '</body></html>'),
               ]
              ]
              
    def get_browser(self):
        br = DefaultProfile.get_browser()
        if self.username is not None and self.password is not None:
            br.open('http://www.nytimes.com/auth/login')
            br.select_form(name='login')
            br['USERID']   = self.username
            br['PASSWORD'] = self.password
            br.submit()
        return br
    
    def parse_feeds(self):
        src = self.browser.open('http://www.nytimes.com/pages/todayspaper/index.html').read().decode('cp1252')
        soup = BeautifulSoup(src)
        
        def feed_title(div):
            return ''.join(div.findAll(text=True, recursive=False)).strip()
        
        articles = {}
        key = None
        for div in soup.findAll(True, 
            attrs={'class':['section-headline', 'story', 'story headline']}):
            
            if div['class'] == 'section-headline':
                key = feed_title(div)
                articles[key] = []
            
            elif div['class'] in ['story', 'story headline']:
                a = div.find('a', href=True)
                if not a:
                    continue
                url = self.print_version(a['href'])
                title = self.tag_to_string(a, use_alt=True).strip()
                description = ''
                pubdate = time.strftime('%a, %d %b', time.localtime())
                summary = div.find(True, attrs={'class':'summary'})
                if summary:
                    description = self.tag_to_string(summary, use_alt=False)
                
                feed = key if key is not None else 'Uncategorized'
                if not articles.has_key(feed):
                    articles[feed] = []
                articles[feed].append(
                    dict(title=title, url=url, date=pubdate, description=description,
                         content=''))
                
            
        return articles
    
    def print_version(self, url):
        return url + '?&pagewanted=print'
