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

import os, time, calendar, operator

from libprs500 import iswindows
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup

def parse_feeds(feeds, browser, print_version, max_articles_per_feed=10):
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
            except:
                continue
            try:
                d['description'] = item.find('description').string
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
