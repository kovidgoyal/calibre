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
'''Logic to create a Newsweek HTML aggregator from RSS feeds'''

import sys, urllib2, time, re, tempfile, os, shutil

from libprs500 import __appname__, iswindows
from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup
from htmlentitydefs import name2codepoint

RSS_FEEDS = [
             ('Cover Story', 'http://feeds.newsweek.com/CoverStory'),
             ('Periscope', 'http://feeds.newsweek.com/newsweek/periscope'),
             ('National News', 'http://feeds.newsweek.com/newsweek/NationalNews'),
             ('World News', 'http://feeds.newsweek.com/newsweek/WorldNews'),
             ('Iraq', 'http://feeds.newsweek.com/newsweek/iraq'),
             ('Health', 'http://feeds.newsweek.com/sections/health'),
             ('Society', 'http://feeds.newsweek.com/newsweek/society'),
             ('Business', 'http://feeds.newsweek.com/newsweek/business'),
             ('Science and Technology', 'http://feeds.newsweek.com/newsweek/TechnologyScience'),
             ('Entertainment', 'http://feeds.newsweek.com/newsweek/entertainment'),
             ('Tip Sheet', 'http://feeds.newsweek.com/newsweek/TipSheet/Highlights'),
             ]

BASE_TEMPLATE=\
u'''
<html>
<body>
<h1>Newsweek</h1>
<b align="right">%(date)s</b>
<p></p>
<h2>Table of Contents</h2>
<ul>
%(toc)s
</ul>
<br />
<hr />
</body>
</html>
'''

SECTION_TEMPLATE=\
u'''
<html>
<body>
<h2>%(title)s</h2>
<p></p>
<h2>Table of Contents</h2>
<ul>
%(toc)s
</ul>
<br />
<hr />
</body>
</html>
'''

_tdir = None
def create_aggregator(sections):
    '''Return aggregator HTML encoded in utf8'''
    toc, sec = u'', 0
    global _tdir
    _tdir = tempfile.mkdtemp(prefix=__appname__)
    for section in sections:
        sec += 1
        secfile = os.path.join(_tdir, 'sec%d.html'%(sec,))
        title, contents = section
        fix = 'file:' if iswindows else ''
        toc += '<li><a href="%s">%s</a></li>\n'%(fix+secfile, title,)
        stoc = u''
        for item in contents:
            desc = item['description'].strip() 
            stoc += '<li><a href="%(link)s">%(title)s</a><br />'%dict(link=item['link'], title=item['title'])
            if desc:
                stoc += '<div style="font-size:small; font-family:sans">%s</div>\n'%(desc,)
            stoc += '</li>\n'
        section = SECTION_TEMPLATE%dict(title=title, toc=stoc)
        open(secfile, 'w').write(section.encode('utf8'))
    index = os.path.join(_tdir, 'index.html')
    src = BASE_TEMPLATE % dict(toc=toc, date=time.strftime('%d %B, %Y', time.localtime()))
    open(index, 'w').write(src.encode('utf8'))
    return index

def get_contents():
    ''' Parse Newsweek RSS feeds to get links to all articles'''
    
    def nstounicode(ns):
        return unicode(str(ns), 'utf8')
    
    def fix_link(link):
        if '?' in link:
            link = link[:link.index('?')]
        return link + 'print/1/displaymode/1098/'
    
    def process_description(tag):
        src = '\n'.join(tag.contents)
        replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo' ]
        for e in replaced_entities:
            ent = '&'+e+';'
            src = src.replace(ent, unichr(name2codepoint[e]))
        return re.compile(r'<a.*?</a>', re.IGNORECASE|re.DOTALL).sub('', src)
    
    pages = []
    for title, url in RSS_FEEDS:
        soup = BeautifulStoneSoup(urllib2.urlopen(url))
        contents = []
        for item in soup.findAll('item'):
            d = { 
                 'title' : nstounicode(item.title.contents[0]),
                 'description': process_description(item.description),
                 'link': fix_link(nstounicode(item.guid.contents[0]))
                 }
            if '&lt;' in d['description']:
                d['description'] = d['description'][:d['description'].index('&lt;')]
            contents.append(d)
        pages.append((title, contents))
    return pages


def initialize(profile):
    print 'Fetching feeds...',
    sys.stdout.flush()
    contents = get_contents()
    print 'done'
    index = create_aggregator(contents)
     
    profile['url'] = 'file:'+ ('' if iswindows else '//') +index

def finalize(profile):
    global _tdir
    shutil.rmtree(_tdir)
