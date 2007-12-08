##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    Costomized to FAZ.NET by S. Dorscht stdoonline@googlemail.com
##    Version 0.10
##
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
Profile to download FAZ.net
'''
import re

from libprs500.ebooks.lrf.web.profiles import DefaultProfile 

class FazNet(DefaultProfile): 

    title = 'FAZ NET' 
    max_recursions = 2 
    html_description = True 
    max_articles_per_feed = 30 

    preprocess_regexps = [
       (re.compile(r'Zum Thema</span>.*?</BODY>', re.IGNORECASE | re.DOTALL), 
        lambda match : ''),
    ]    


    def get_feeds(self): 
        return [ ('FAZ.NET', 'http://www.faz.net/s/Rub/Tpl~Epartner~SRss_.xml') ] 

    def print_version(self, url): 
        return url.replace('.html?rss_aktuell', '~Afor~Eprint.html') 

