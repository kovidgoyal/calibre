##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    Costomized to Dilbert by S. Dorscht and "Stenis"
##    Version 0.02
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
Fetch Dilbert.
'''


from libprs500.ebooks.lrf.web.profiles import DefaultProfile

import re

class Dilbert(DefaultProfile):

    title = 'Dilbert'
    timefmt = ' [%d %b %Y]'
    max_recursions = 1
    max_articles_per_feed = 6
    html_description = True
    no_stylesheets = True

    def get_feeds(self): 
        return [ ('Dilbert', 'http://feeds.feedburner.com/tapestrydilbert') ] 

