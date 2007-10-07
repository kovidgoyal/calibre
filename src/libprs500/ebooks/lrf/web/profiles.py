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
'''Profiles for known websites.'''
import re

from libprs500.ebooks.lrf.web.newsweek import initialize as newsweek_initialize
from libprs500.ebooks.lrf.web.newsweek import finalize as newsweek_finalize
from libprs500.ebooks.lrf.web.nytimes import initialize as nytimes_initialize
from libprs500.ebooks.lrf.web.nytimes import finalize as nytimes_finalize
from libprs500.ebooks.lrf.web.bbc import initialize as bbc_initialize
from libprs500.ebooks.lrf.web.bbc import finalize as bbc_finalize
from libprs500.ebooks.lrf.web.economist import initialize as economist_initialize
from libprs500.ebooks.lrf.web.economist import finalize as economist_finalize


profiles = {
            'default' : {
                         'url'               : '',    # The URL of the website
                         'title'             : '',    # The title to use for the LRF file
                         'max_recursions'    : 1,     # Number of levels of links to follow
                         'max_files'         : 1000,  # Maximum number of files to download
                         'delay'             : 0,     # Delay between consecutive downloads
                         'timeout'           : 10,    # Timeout for fetching files from server in seconds
                         'timefmt'           : ' [%a %d %b %Y]',
                         'no_stylesheets'    : False, # Download stylesheets 
                         'match_regexps'     : [],    # List of regular expressions that determines which links to follow
                         'filter_regexps'    : [],    # List of regular expressions that determines which links to ignore
                         # Only one of match_regexps or filter_regexps should be defined
                         'html2lrf_options'  : [],    # List of options to pass to html2lrf
                         'preprocess_regexps': [],    # List of regexp substitution rules to run on the downloaded HTML before running html2lrf
                         # See the profiles below for examples of these settings. 
                       },
                       
            'nytimes' : {
                         'initialize'          : nytimes_initialize,
                         'finalize'            : nytimes_finalize,
                         
                         'preprocess_regexps' :
                         [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
                          [
                           # Remove header bar
                           (r'(<body.*?>).*?<h1', lambda match: match.group(1)+'<h1'),
                           (r'<div class="articleTools">.*></ul>', lambda match : ''),
                           # Remove footer bar
                           (r'<\!--  end \#article -->.*', lambda match : '</body></html>'),
                           (r'<div id="footer">.*', lambda match : '</body></html>'),
                           ]
                          ],
                         },
                         
            'bbc'     : {
                          'initialize'          : bbc_initialize,
                          'finalize'            : bbc_finalize,
                          'preprocess_regexps' :
                         [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
                          [
                           # Remove footer from individual stories
                           (r'<div class=.footer.>.*?Published', 
                            lambda match : '<p></p><div class="footer">Published'),
                           # Add some style info in place of disabled stylesheet
                           (r'<link.*?type=.text/css.*?>', lambda match :
                            '''<style type="text/css">
                                .headline {font-size: x-large;}
                                .fact { padding-top: 10pt  }
                                </style>'''),
                           ]
                          ],
                          },
            
            'newsweek' : {
                          'initialize'          : newsweek_initialize,
                          'finalize'            : newsweek_finalize,
                          'no_stylesheets'      : True,
                          'preprocess_regexps'  :
                         [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
                          [
                           # Make fonts larger
                           (r'<style.*?\.copyright.*?</style>', 
                            lambda match : \
                        '''<style type="text/css">'''
                        '''updateTime{font:small Arial;color:#000000;}'''
                        '''.credit{font:small Arial;color:#999999;}'''
                        '''.head{font:bold 18pt x-large;color:#CC0000;}'''
                        '''.abstract{font:14pt large Verdana;color:#000000;}'''
                        '''.title{font:bold;color:#000000;}'''
                        '''.source{font:bold small Verdana;color:#CC0000;}'''
                        '''.footerLink{font:bold Verdana;color:#000000;}'''
                        '''.caption{font: Verdana;color:#000000;}'''
                        '''.textBodyBlack, .copyright{font: Verdana;color:#000000;}'''
                        '''.copyright{font-style:italic;}'''
                        '''</style>'''
                            ),
                           ]
                          ],
                          }, 
                          
            'economist' : {
                           'initialize'          : economist_initialize,
                           'finalize'            : economist_finalize,
                           'preprocess_regexps' :
                           [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
                            [
                             # Remove advert
                             (r'<noscript.*?</noscript>', lambda match: ''),
                             ]
                            ], 
                           },                                   
            }

for key in profiles.keys():
    if key == 'default':
        continue
    newd = profiles['default'].copy()
    newd.update(profiles[key])
    profiles[key] = newd

def profile_to_command_line_options(profile):
    args = []
    args.append('--max-recursions='+str(profile['max_recursions']))
    args.append('--delay='+str(profile['delay']))
    for i in profile['match_regexps']:
        args.append('--match-regexp="'+i+'"')
    for i in profile['filter_regexps']:
        args.append('--filter-regexp="'+i+'"')
    return args