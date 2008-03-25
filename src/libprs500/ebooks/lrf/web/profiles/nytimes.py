__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
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
    
    def get_feeds(self):
        src = self.browser.open('http://www.nytimes.com/services/xml/rss/index.html').read()
        soup = BeautifulSoup(src[src.index('<html'):])
        feeds = []
        for link in soup.findAll('link', attrs={'type':'application/rss+xml'}):
            if link['title'] not in ['NYTimes.com Homepage', 'Obituaries', 'Pogue\'s Posts', 
                                     'Dining & Wine', 'Home & Garden', 'Multimedia',
                                     'Most E-mailed Articles', 
                                     'Automobiles', 'Fashion & Style', 'Television News',
                                     'Education']:
                feeds.append((link['title'], link['href'].replace('graphics8', 'www')))            
        
        return feeds
    
    
    def parse_feeds(self):
        if self.lrf: # The new feed causes the SONY Reader to crash
            return DefaultProfile.parse_feeds(self)
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
