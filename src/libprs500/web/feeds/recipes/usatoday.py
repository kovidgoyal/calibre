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
'''
usatoday.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe
import re

class USAToday(BasicNewsRecipe):

    title = 'USA Today'
    timefmt  = ' [%d %b %Y]'
    max_articles_per_feed = 20
    no_stylesheets = True
    extra_css = '''
    .inside-head { font: x-large bold } 
    .inside-head2 { font: x-large bold }
    .inside-head3 { font: x-large bold }
    .byLine { font: large }
    '''
    html2lrf_options = ['--ignore-tables']

    preprocess_regexps = [
        (re.compile(r'<BODY.*?<!--Article Goes Here-->', re.IGNORECASE | re.DOTALL), lambda match : '<BODY>'),
        (re.compile(r'<!--Article End-->.*?</BODY>', re.IGNORECASE | re.DOTALL), lambda match : '</BODY>'),
        ]
    
    feeds =  [
                ('Top Headlines', 'http://rssfeeds.usatoday.com/usatoday-NewsTopStories'),
                ('Sport Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomSports-TopStories'),
                ('Tech Headlines', 'http://rssfeeds.usatoday.com/usatoday-TechTopStories'),
                ('Travel Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomTravel-TopStories'),
                ('Money Headlines', 'http://rssfeeds.usatoday.com/UsatodaycomMoney-TopStories'),
                ('Entertainment Headlines', 'http://rssfeeds.usatoday.com/usatoday-LifeTopStories'),
                ('Weather Headlines', 'http://rssfeeds.usatoday.com/usatoday-WeatherTopStories'),
                ('Most Popular', 'http://rssfeeds.usatoday.com/Usatoday-MostViewedArticles'),
                ]
    
    ## Getting the print version 
    
    def print_version(self, url):
        return 'http://www.printthis.clickability.com/pt/printThis?clickMap=printThis&fb=Y&url=' + url
    