##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    Costomized to spiegel.de by S. Dorscht stdoonline@googlemail.com
##    Version 0.10
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
Fetch Spiegel Online.
'''

from libprs500.ebooks.lrf.web.profiles import DefaultProfile

import re

class SpiegelOnline(DefaultProfile): 
    
    title = 'Spiegel Online' 
    timefmt = ' [ %Y-%m-%d %a]'
    max_recursions = 2
    max_articles_per_feed = 40
    use_pubdate = False
    no_stylesheets = True

    preprocess_regexps = \
        [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
            [
             # Remove Zum Thema footer
             (r'<div class="spArticleCredit.*?</body>', lambda match: '</body>'),
             ]
            ]
    
    def get_feeds(self): 
        return [ ('Spiegel Online', 'http://www.spiegel.de/schlagzeilen/rss/0,5291,,00.xml') ] 

       
    def print_version(self,url):
        tokens = url.split(',')
        tokens[-2:-2] = ['druck|']
        return ','.join(tokens).replace('|,','-')
