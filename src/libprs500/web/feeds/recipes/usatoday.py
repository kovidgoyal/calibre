#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
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
    
