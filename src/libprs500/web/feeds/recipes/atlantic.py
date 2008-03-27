#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
theatlantic.com
'''

from libprs500.web.feeds.news import BasicNewsRecipe

class TheAtlantic(BasicNewsRecipe):
    
    title      = 'The Atlantic'
    __author__ = 'Kovid Goyal'
    description = 'Current affairs and politics focussed on the US'
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
