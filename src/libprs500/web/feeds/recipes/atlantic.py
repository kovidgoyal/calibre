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
theatlantic.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe

class TheAtlantic(BasicNewsRecipe):
    
    title = 'The Atlantic'
    INDEX = 'http://www.theatlantic.com/doc/current'
    
    remove_tags_before = dict(name='div', id='storytop')
    remove_tags        = [dict(name='div', id='seealso')]
    extra_css          = '#bodytext {line-height: 1}'
    
    def parse_index(self):
        articles = []
        
        soup = self.index_to_soup(self.INDEX)
        
        issue = soup.find('span', attrs={'class':'issue'})
        if issue:
            self.timefmt = ' [%s]'%self.tag_to_string(issue).rpartition('|')[-1].strip().replace('/', '-')
            
        cover = soup.find('img', alt='feature image', src=True)
        if cover is not None:
            self.cover_url = 'http://theatlantic.com'+cover['src']
        else:
            raise 'a'
        
        for item in soup.findAll('div', attrs={'class':'item'}):
            a = item.find('a')
            if a and a.has_key('href'):
                url = a['href']
                url = 'http://www.theatlantic.com/'+url.replace('/doc', 'doc/print')
                title = self.tag_to_string(a)
                byline = item.find(attrs={'class':'byline'})
                date = self.tag_to_string(byline) if byline else ''
                description = ''
                articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':description
                                })
                
        
        return [('Current Issue', articles)]