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

import os, time, calendar, operator, re

from libprs500 import iswindows
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup
from htmlentitydefs import name2codepoint

def process_html_description(tag):
        src = '\n'.join(tag.contents)
        replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo' ]
        for e in replaced_entities:
            ent = '&'+e+';'
            src = src.replace(ent, unichr(name2codepoint[e]))
        return re.compile(r'<a.*?</a>', re.IGNORECASE|re.DOTALL).sub('', src)

def parse_feeds(feeds, browser, print_version, 
                max_articles_per_feed=10, 
                html_description=False,
                oldest_article=7):
    '''
    @param print_version: Callable that takes a url string and returns the url to 
                          printable version of the article pointed to by the original url.
    @param max_articles_per_feed: Maximum number of articles to download from each feed
    @param html_description: If true the atricles descriptions are processed as HTML
    @param oldest_article: A number in days. No articles older than now - oldest_aticle 
                           will be downloaded.  
    '''
    articles = {}
    for title, url in feeds:
        src = browser.open(url).read()
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
                    'url'      : print_version(item.find('guid').string),
                    'timestamp': calendar.timegm(time.strptime(pubdate, 
                                                    '%a, %d %b %Y %H:%M:%S %Z')),
                    'date'     : pubdate
                    }
                delta = time.time() - d['timestamp']
                if delta > oldest_article*3600*24:
                    continue 
            except:
                continue
            try:
                desc = item.find('description')
                d['description'] = process_html_description(desc) if  html_description else desc.string                    
            except:
                d['description'] = ''
            articles[title].append(d)
        articles[title].sort(key=operator.itemgetter('timestamp'), reverse=True)
        articles[title][max_articles_per_feed:] = []
        for item in articles[title]:
            item.pop('timestamp')
    return articles


def build_index(title, articles, dir):
    '''Build an RSS based index.html'''

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
        cfile = os.path.join(dir, 'category'+str(cnum)+'.html')
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
             categories=clist, title=title)
    index = os.path.join(dir, 'index.html')
    open(index, 'wb').write(src.encode('utf-8'))
    return index
