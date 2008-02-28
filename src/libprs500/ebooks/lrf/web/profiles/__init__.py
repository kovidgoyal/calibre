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
Contains the Base Profiles that can be used to easily create profiles to download
particular websites.  
'''

import tempfile, time, calendar, re, operator, atexit, shutil, os
from htmlentitydefs import name2codepoint

from libprs500 import __appname__, iswindows, browser
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup, NavigableString, CData, Tag


class DefaultProfile(object):
    
    #: The title to use for the LRF file
    #: @type: string    
    title                 = 'Default Profile'    
    
    #: Maximum number of articles to download from each feed
    #: @type: integer
    max_articles_per_feed = 10     
    
    #: If True process the <description> element of the feed as HTML
    #: @type: boolean
    html_description      = True  
    
    #: How many days old should the oldest article downloaded from the feeds be
    #: @type: integer
    oldest_article        = 7
    
    #: Recommend frequency at which to download this profile. In days.
    recommended_frequency = 7
    
    #: Number of levels of links to follow
    #: @type: integer
    max_recursions        = 1
    
    #: Maximum number of files to download
    #: @type: integer
    max_files             = 3000
    
    #: Delay between consecutive downloads in seconds
    #: @type: integer
    delay                 = 0
    
    #: Timeout for fetching files from server in seconds
    #: @type: integer
    timeout               = 10
    
    #: The format string for the date shown on the first page
    #: @type: string
    timefmt               = ' [%a %d %b %Y]'
    
    #: The order of elements to search for a URL when parsing the RSS feed. You 
    #: can replace these elements by completely arbitrary elements to customize
    #: feed processing. 
    #: @type: list of strings
    url_search_order      = ['guid', 'link']
    
    #: The format string used to parse the publication date in the RSS feed. 
    #: If set to None some default heuristics are used, these may fail, 
    #: in which case set this to the correct string or re-implement 
    #: L{DefaultProfile.strptime} in your subclass.
    #: @type: string or None 
    pubdate_fmt           = None  
    
    #: If True will look for a publication date for each article. 
    #: If False assumes the publication date is the current time.
    #: @type: boolean
    use_pubdate           = True, 
    
    #: Max number of characters in the short description.
    #: Used by L{FullContentProfile}
    #: @type: integer
    summary_length        = 500
    
    #: If True stylesheets are not downloaded and processed
    #: Convenient flag to disable loading of stylesheets for websites
    #: that have overly complex stylesheets unsuitable for conversion
    #: to ebooks formats
    #: @type: boolean
    no_stylesheets        = False
    
    #: If False articles with the same title in the same feed 
    #: are not downloaded multiple times
    #: @type: boolean 
    allow_duplicates      = False 
    
    #: If True the GUI will ask the user for a username and password 
    #: to use while downloading
    #: @type: boolean
    needs_subscription    = False
    
    #: Specify an override encoding for sites that have an incorrect
    #: charset specification. THe most common being specifying latin1 and
    #: using cp1252 
    encoding = None
    
    #: List of regular expressions that determines which links to follow
    #: If empty, it is ignored.
    #: Only one of L{match_regexps} or L{filter_regexps} should be defined
    #: @type: list of strings
    match_regexps         = []
    
    #: List of regular expressions that determines which links to ignore
    #: If empty it is ignored
    #: Only one of L{match_regexps} or L{filter_regexps} should be defined
    #: @type: list of strings
    filter_regexps        = []    
    
    #: List of options to pass to html2lrf, to customize conversion
    #: to LRF
    #: @type: list of strings
    html2lrf_options   = []
        
    #: List of regexp substitution rules to run on the downloaded HTML. Each element of the 
    #: list should be a two element tuple. The first element of the tuple should
    #: be a compiled regular expression and the second a callable that takes
    #: a single match object and returns a string to replace the match.
    #: @type: list of tuples
    preprocess_regexps = []
    
    # See the built-in profiles for examples of these settings.
    
    #: The URL of the website
    #: @type: string
    url                   = ''
    
    feeds = []
    CDATA_PAT = re.compile(r'<\!\[CDATA\[(.*?)\]\]>', re.DOTALL)

    def get_feeds(self):
        '''
        Return a list of RSS feeds to fetch for this profile. Each element of the list
        must be a 2-element tuple of the form (title, url).
        '''
        if not self.feeds:
            raise NotImplementedError
        return self.feeds
    
    @classmethod
    def print_version(cls, url):
        '''
        Take a URL pointing to an article and returns the URL pointing to the
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
    
    
    
    
    def __init__(self, logger, verbose=False, username=None, password=None):
        self.logger = logger
        self.username = username
        self.password = password
        self.verbose  = verbose
        self.temp_dir = tempfile.mkdtemp(prefix=__appname__+'_')
        self.browser = self.get_browser()
        try:
            self.url = 'file:'+ ('' if iswindows else '//') + self.build_index()
        except NotImplementedError:
            self.url = None
        atexit.register(cleanup, self.temp_dir)
    
    def build_index(self):
        '''Build an RSS based index.html'''
        articles = self.parse_feeds()
        encoding = 'utf-8' if self.encoding is None else self.encoding 
        def build_sub_index(title, items):
            ilist = ''
            li = u'<li><a href="%(url)s">%(title)s</a> <span style="font-size: x-small">[%(date)s]</span><br/>\n'+\
                u'<div style="font-size:small; font-family:sans">%(description)s<br /></div></li>\n'
            for item in items:
                if not item.has_key('date'):
                    item['date'] = time.strftime('%a, %d %b', time.localtime())
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
            open(cfile, 'wb').write(src.encode(encoding))
                        
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
        open(index, 'wb').write(src.encode(encoding))
        
        return index

    
    @classmethod
    def tag_to_string(cls, tag, use_alt=True):
        '''
        Convenience method to take a BeautifulSoup Tag and extract the text from it
        recursively, including any CDATA sections and alt tag attributes.
        @param use_alt: If True try to use the alt attribute for tags that don't have any textual content
        @type use_alt: boolean
        @return: A unicode (possibly empty) object
        @rtype: unicode string
        '''
        if not tag:
            return ''
        if isinstance(tag, basestring):
            return tag
        strings = []
        for item in tag.contents:
            if isinstance(item, (NavigableString, CData)):
                strings.append(item.string)
            elif isinstance(item, Tag):
                res = cls.tag_to_string(item)
                if res:
                    strings.append(res)
                elif use_alt and item.has_key('alt'):
                    strings.append(item['alt'])
        return u''.join(strings) 
    
    def get_article_url(self, item):
        '''
        Return the article URL given an item Tag from a feed, or None if no valid URL is found
        @type item: BeatifulSoup.Tag
        @param item: A BeautifulSoup Tag instance corresponding to the <item> tag from a feed.
        @rtype: string or None
        '''
        url = None
        for element in self.url_search_order:
            url = item.find(element.lower())
            if url:
                break
        return url
        
    
    def parse_feeds(self, require_url=True):
        '''
        Create list of articles from a list of feeds.
        @param require_url: If True skip articles that don't have a link to a HTML page with the full article contents.
        @type require_url: boolean
        @rtype: dictionary
        @return: A dictionary whose keys are feed titles and whose values are each
        a list of dictionaries. Each list contains dictionaries of the form::
            {
            'title'       : article title,
            'url'         : URL of print version,
            'date'        : The publication date of the article as a string,
            'description' : A summary of the article
            'content'     : The full article (can be an empty string). This is used by FullContentProfile
            }
        '''
        added_articles = {}
        feeds = self.get_feeds()
        articles = {}
        for title, url in feeds:
            try:
                src = self.browser.open(url).read()
            except Exception, err:
                self.logger.error('Could not fetch feed: %s\nError: %s'%(url, err))
                if self.verbose:
                    self.logger.exception(' ')
                continue
            
            articles[title] = []
            added_articles[title] = []
            soup = BeautifulStoneSoup(src)
            for item in soup.findAll('item'):
                try:
                    if self.use_pubdate:
                        pubdate = item.find('pubdate')
                        if not pubdate:
                            pubdate = item.find('dc:date')
                        if not pubdate or not pubdate.string:
                            self.logger.debug('Skipping article as it does not have publication date')
                            continue
                        pubdate = self.tag_to_string(pubdate)
                        pubdate = pubdate.replace('+0000', 'GMT')
                    
                    url = self.get_article_url(item)
                    url = self.tag_to_string(url)
                    if require_url and not url:
                        self.logger.debug('Skipping article as it does not have a link url')
                        continue
                    purl = url
                    try:
                        purl = self.print_version(url)
                    except Exception, err:
                        self.logger.debug('Skipping %s as could not find URL for print version. Error:\n%s'%(url, err))
                        continue
                    
                    content = item.find('content:encoded')
                    if not content:
                        content = item.find('description')
                    if content:
                        content = self.process_html_description(content, strip_links=False)
                    else:
                        content = ''
                        
                    d = { 
                        'title'    : self.tag_to_string(item.find('title')),                 
                        'url'      : purl,
                        'timestamp': self.strptime(pubdate) if self.use_pubdate else time.time(),
                        'date'     : pubdate if self.use_pubdate else time.ctime(),
                        'content'  : content,
                        }
                    delta = time.time() - d['timestamp']
                    if not self.allow_duplicates:
                        if d['title'] in added_articles[title]:
                            continue
                        added_articles[title].append(d['title'])
                    if delta > self.oldest_article*3600*24:
                        continue
                    
                except Exception, err:
                    if self.verbose:
                        self.logger.exception('Error parsing article:\n%s'%(item,))
                    continue
                try:
                    desc = ''
                    for c in item.findAll('description'):
                        desc = self.tag_to_string(c)
                        if desc:
                            break
                    d['description'] = self.process_html_description(desc) if  self.html_description else desc.string                    
                except:
                    d['description'] = ''
                articles[title].append(d)
            articles[title].sort(key=operator.itemgetter('timestamp'), reverse=True)
            articles[title] = articles[title][:self.max_articles_per_feed+1]
            for item in articles[title]:
                item.pop('timestamp')
            if not articles[title]:
                articles.pop(title)
        return articles

    
    def cleanup(self):
        '''
        Called after LRF file has been generated. Use it to do any cleanup like 
        logging out of subscription sites, etc.
        '''
        pass
    
    @classmethod
    def process_html_description(cls, tag, strip_links=True):
        '''
        Process a <description> tag that contains HTML markup, either 
        entity encoded or escaped in a CDATA section. 
        @return: HTML
        @rtype: string
        '''
        src = '\n'.join(tag.contents) if hasattr(tag, 'contents') else tag
        match = cls.CDATA_PAT.match(src.lstrip())
        if match:
            src = match.group(1)
        else:
            replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo' ]
            for e in replaced_entities:
                ent = '&'+e+';'
                src = src.replace(ent, unichr(name2codepoint[e]))
        if strip_links:
            src = re.compile(r'<a.*?>(.*?)</a>', re.IGNORECASE|re.DOTALL).sub(r'\1', src)
        
        return src 

    
    DAY_MAP        = dict(Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5, Sat=6)
    FULL_DAY_MAP   = dict(Sunday=0, Monday=1, Tueday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6) 
    MONTH_MAP      = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6, Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)
    FULL_MONTH_MAP = dict(January=1, February=2, March=3, April=4, May=5, June=6, 
                      July=7, August=8, September=9, October=10, 
                      November=11, December=12)
        
    @classmethod
    def strptime(cls, src):
        ''' 
        Take a string and return the date that string represents, in UTC as
        an epoch (i.e. number of seconds since Jan 1, 1970). This function uses
        a bunch of heuristics and is a prime candidate for being overridden in a 
        subclass.
        @param src: Timestamp as a string
        @type src: string
        @return: time ans a epoch
        @rtype: number 
        '''        
        delta = 0
        zone = re.search(r'\s*(\+\d\d\:{0,1}\d\d)', src)
        if zone:
            delta = zone.group(1)
            hrs, mins = int(delta[1:3]), int(delta[-2:].rstrip())
            delta = 60*(hrs*60 + mins) * (-1 if delta.startswith('-') else 1)
            src = src.replace(zone.group(), '')
        if cls.pubdate_fmt is None:
            src = src.strip().split()
            try:
                src[0] = str(cls.DAY_MAP[src[0][:-1]])+','
            except KeyError:
                src[0] = str(cls.FULL_DAY_MAP[src[0][:-1]])+','
            try:
                src[2] = str(cls.MONTH_MAP[src[2]])
            except KeyError:
                src[2] = str(cls.FULL_MONTH_MAP[src[2]])
            fmt = '%w, %d %m %Y %H:%M:%S'
            src = src[:5] # Discard extra information
            try:
                time_t = time.strptime(' '.join(src), fmt)
            except ValueError:
                time_t = time.strptime(' '.join(src), fmt.replace('%Y', '%y'))
            return calendar.timegm(time_t)-delta
        else:
            return calendar.timegm(time.strptime(src, cls.pubdate_fmt))
    
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
        
    
class FullContentProfile(DefaultProfile):
    '''
    This profile is designed for feeds that embed the full article content in the RSS file.
    '''
    
    max_recursions = 0
    article_counter = 0
    
    
    def build_index(self):
        '''Build an RSS based index.html. '''
        articles = self.parse_feeds(require_url=False)
        
        def build_sub_index(title, items):
            ilist = ''
            li = u'<li><a href="%(url)s">%(title)s</a> <span style="font-size: x-small">[%(date)s]</span><br/>\n'+\
                u'<div style="font-size:small; font-family:sans">%(description)s<br /></div></li>\n'
            for item in items:
                content = item['content']
                if not content:
                    self.logger.debug('Skipping article as it has no content:%s'%item['title'])
                    continue
                item['description'] = cutoff(item['description'], self.summary_length)+'&hellip;'
                self.article_counter = self.article_counter + 1
                url = os.path.join(self.temp_dir, 'article%d.html'%self.article_counter)
                item['url'] = url
                open(url, 'wb').write((u'''\
                    <html>
                    <body>
                    <h2>%s</h2>
                    <div>
                    %s
                    </div>
                    </body>
                    </html>'''%(item['title'], content)).encode('utf-8')
                    )
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

def cutoff(src, pos, fuzz=50):
    si = src.find(';', pos)
    if si > 0 and si-pos > fuzz:
        si = -1
    gi = src.find('>', pos)
    if gi > 0 and gi-pos > fuzz:
        gi = -1
    npos = max(si, gi)
    if npos < 0:
        npos = pos
    return src[:npos+1]

def create_class(src):
    environment = {'FullContentProfile':FullContentProfile, 'DefaultProfile':DefaultProfile}
    exec src in environment
    for item in environment.values():
        if hasattr(item, 'build_index'):
            if item.__name__ not in ['DefaultProfile', 'FullContentProfile']:
                return item
   
def cleanup(tdir):
    try:
        if os.path.isdir(tdir):
            shutil.rmtree(tdir)
    except:
        pass
    