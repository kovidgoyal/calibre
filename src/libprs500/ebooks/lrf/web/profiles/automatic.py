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
import os

from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup
from libprs500 import iswindows
from libprs500.ebooks.chardet import xml_to_unicode

class AutomaticRSSProfile(DefaultProfile):
    '''
    Make downloading of RSS feeds completely automatic. Only input 
    required is the URL of the feed.
    '''
    
    max_recursions = 2
    
    def __init__(self, *args, **kwargs):
        self.cindex = 1
        DefaultProfile.__init__(*args, **kwargs)
    
    def fetch_content(self, index):
        raw = open(index, 'rb').read()
        if self.encoding:
            raw = raw.decode(self.encoding)
            enc = self.encoding
        else:
            raw, enc = xml_to_unicode(raw)
        isoup = BeautifulSoup(raw)
        for a in isoup.findAll('a', href=True):
            src = a['href']
            if src.startswith('file:'):
                src = src[5:]
            if os.access(src, os.R_OK):
                self.fetch_content(src)
                continue
            try:
                src = self.browser.open(src).read()
            except:
                continue
            soup  = BeautifulSoup(src)
            header, content = [], []
            head = soup.find('head')
            if head is not None:
                for style in head('style'):
                    header.append(unicode(style))
            body = soup.find('body')
            if body is None:
                continue
            for tag in body(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                in_table = False
                c = tag.parent
                while c is not None:
                    if c.name == 'table':
                        in_table = True
                        break
                    c = c.parent
                if in_table:
                    continue
                content.append(unicode(tag))
                
            cfile = 'content%d.html'%self.cindex
            self.cindex += 1
            cfile = os.path.join(os.path.dirname(index), cfile)
            html = '<html>\n<head>%s</head>\n<body>%s</body></html>'%('\n'.join(header), '\n'.join(content))
            
            open(cfile, 'wb').write(html.encode(enc))
            a['href'] = ('file:' if iswindows else '') + cfile
        open(index, 'wb').write(unicode(isoup).encode(enc)) 
    
    def build_index(self):
        index = DefaultProfile.build_index(self)
        self.fetch_content(index)
    