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
portfolio.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe

class Portfolio(BasicNewsRecipe):
    
    title                = 'Portfolio'
    use_embedded_content = True
    timefmt              = ' [%a, %b %d, %Y]'
    html2lrf_options     = ['--ignore-tables']
    
    feeds = [ 
                ('Business Travel', 'http://feeds.portfolio.com/portfolio/businesstravel'), 
                ('Careers', 'http://feeds.portfolio.com/portfolio/careers'), 
                ('Culture and Lifestyle', 'http://feeds.portfolio.com/portfolio/cultureandlifestyle'), 
                ('Executives','http://feeds.portfolio.com/portfolio/executives'), 
                ('News and Markets', 'http://feeds.portfolio.com/portfolio/news'), 
                ('Business Spin', 'http://feeds.portfolio.com/portfolio/businessspin'), 
                ('Capital', 'http://feeds.portfolio.com/portfolio/capital'), 
                ('Daily Brief', 'http://feeds.portfolio.com/portfolio/dailybrief'), 
                ('Market Movers', 'http://feeds.portfolio.com/portfolio/marketmovers'), 
                ('Mixed Media', 'http://feeds.portfolio.com/portfolio/mixedmedia'), 
                ('Odd Numbers', 'http://feeds.portfolio.com/portfolio/oddnumbers'), 
                ('Playbook', 'http://feeds.portfolio.com/portfolio/playbook'), 
                ('Tech Observer', 'http://feeds.portfolio.com/portfolio/thetechobserver'), 
                ('World According to ...', 'http://feeds.portfolio.com/portfolio/theworldaccordingto'), 
            ]