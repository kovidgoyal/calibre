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
'''

import tempfile, time, calendar, re, operator
from htmlentitydefs import name2codepoint

from libprs500 import __appname__, iswindows, browser
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup


class DefaultProfile(object):
    
    url                   = ''    # The URL of the website
    title                 = 'Default Profile'    # The title to use for the LRF file
    max_articles_per_feed = 10    # Maximum number of articles to download from each feed 
    html_description      = False # If True process the <description> element of the feed as HTML
    oldest_article        = 7     # How many days old should the oldest article downloaded from the feeds be?
    max_recursions        = 1     # Number of levels of links to follow
    max_files             = 3000  # Maximum number of files to download
    delay                 = 0     # Delay between consecutive downloads
    timeout               = 10    # Timeout for fetching files from server in seconds
    timefmt               = ' [%a %d %b %Y]' # The format of the date shown on the first page
    no_stylesheets        = False # Download stylesheets only if False 
    match_regexps         = []    # List of regular expressions that determines which links to follow
    filter_regexps        = []    # List of regular expressions that determines which links to ignore
    # Only one of match_regexps or filter_regexps should be defined
    
    html2lrf_options   = []    # List of options to pass to html2lrf
    # List of regexp substitution rules to run on the downloaded HTML. Each element of the 
    # list should be a two element tuple. THe first element of the tuple should
    # be a compiled regular expression and the second a callable that takes
    # a single match object and returns a string to replace the match.
    preprocess_regexps = []
    
    # See the built-in profiles for examples of these settings.
    
    def get_feeds(self):
        '''
        Return a list of RSS feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url).
        '''
        raise NotImplementedError
    
    @classmethod
    def print_version(cls, url):
        '''
        Takea a URL pointing to an article and returns the URL pointing to the
        print version of the article.
        '''
        return url
    
    @classmethod
    def get_browser(cls):
        '''
        Return a browser instance used to fetch documents from the web.
        
        If your profile requires that you login first, override this method
        in your subclass. See for example the nytimes profile.
        '''
        return browser()
    
    ########################################################################
    ###################### End of customizable portion #####################
    ########################################################################
    
    
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.temp_dir = tempfile.mkdtemp(prefix=__appname__+'_')
        self.browser = self.get_browser()
        self.url = 'file:'+ ('' if iswindows else '//') + self.build_index()
    
    def __del__(self):
        import os, shutil
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def build_index(self):
        '''Build an RSS based index.html'''
        import os
        articles = self.parse_feeds()
        
    
        def build_sub_index(title, items):
            ilist = ''
            li = u'<li><a href="%(url)s">%(title)s</a> <span style="font-size: x-small">[%(date)s]</span><br/>\n'+\
                u'<div style="font-size:small; font-family:sans">%(description)s<br /></div></li>\n'
            for item in items:
                ilist += li%item
            return u'''\
            <html>
            <body>
            <h2>%(title)s</h2>
            <ul>
            %(items)s
            </ul>
            </body>
            </html>
            '''%dict(title=title, items=ilist.rstrip())        
        
        cnum = 0
        clist = ''
        categories = articles.keys()
        categories.sort()
        for category in categories:
            cnum  += 1
            cfile = os.path.join(self.temp_dir, 'category'+str(cnum)+'.html')
            prefix = 'file:' if iswindows else ''
            clist += u'<li><a href="%s">%s</a></li>\n'%(prefix+cfile, category)
            src = build_sub_index(category, articles[category])
            open(cfile, 'wb').write(src.encode('utf-8'))        
        
        src = '''\
        <html>
        <body>
        <h1>%(title)s</h1>
        <div style='text-align: right; font-weight: bold'>%(date)s</div>
        <ul>
        %(categories)s
        </ul>
        </body>
        </html>
        '''%dict(date=time.strftime('%a, %d %B, %Y', time.localtime()), 
                 categories=clist, title=self.title)
        index = os.path.join(self.temp_dir, 'index.html')
        open(index, 'wb').write(src.encode('utf-8'))
        return index

    
    def parse_feeds(self):
        feeds = self.get_feeds()
        articles = {}
        for title, url in feeds:
            try:
                src = self.browser.open(url).read()
            except Exception, err:
                print 'Could not fetch feed: %s\nError: %s'%(url, err)
                continue
            
            articles[title] = []
            soup = BeautifulStoneSoup(src)
            for item in soup.findAll('item'):
                try:
                    pubdate = item.find('pubdate').string
                    if not pubdate:
                        continue
                    pubdate = pubdate.replace('+0000', 'GMT')
                    d = { 
                        'title'    : item.find('title').string,                 
                        'url'      : self.print_version(item.find('guid').string),
                        'timestamp': calendar.timegm(self.strptime(pubdate)),
                        'date'     : pubdate
                        }
                    delta = time.time() - d['timestamp']
                    if delta > self.oldest_article*3600*24:
                        continue
                     
                except Exception, err:
                    continue
                try:
                    desc = item.find('description')
                    d['description'] = self.process_html_description(desc) if  self.html_description else desc.string                    
                except:
                    d['description'] = ''
                articles[title].append(d)
            articles[title].sort(key=operator.itemgetter('timestamp'), reverse=True)
            articles[title][self.max_articles_per_feed:] = []
            for item in articles[title]:
                item.pop('timestamp')
            if not articles[title]:
                articles.pop(title)
        return articles

    
    @classmethod
    def process_html_description(cls, tag):
        src = '\n'.join(tag.contents)
        replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo' ]
        for e in replaced_entities:
            ent = '&'+e+';'
            src = src.replace(ent, unichr(name2codepoint[e]))
        return re.compile(r'<a.*?</a>', re.IGNORECASE|re.DOTALL).sub('', src)

    
    DAY_MAP   = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
    MONTH_MAP = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
    FULL_MONTH_MAP = dict(January=1, February=2, March=3, April=4, May=5, June=6, 
                      July=7, August=8, September=9, October=10, 
                      November=11, December=12)
        
    @classmethod
    def strptime(cls, src):
        src = src.strip().split()
        src[0] = str(cls.DAY_MAP[src[0][:-1]])+','
        try:
            src[2] = str(cls.MONTH_MAP[src[2]])
        except KeyError:
            src[2] = str(cls.FULL_MONTH_MAP[src[2]])
        return time.strptime(' '.join(src), '%w, %d %m %Y %H:%M:%S %Z')
    
    def command_line_options(self):
        args = []
        args.append('--max-recursions='+str(self.max_recursions))
        args.append('--delay='+str(self.delay))
        args.append('--max-files='+str(self.max_files))
        for i in self.match_regexps:
            args.append('--match-regexp="'+i+'"')
        for i in self.filter_regexps:
            args.append('--filter-regexp="'+i+'"')
        return args
        
    
