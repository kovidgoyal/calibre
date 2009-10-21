#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
theatlantic.com
'''
import re
from calibre.web.feeds.news import BasicNewsRecipe

class TheAtlantic(BasicNewsRecipe):

    title      = 'The Atlantic'
    __author__ = 'Kovid Goyal and Sujata Raman'
    description = 'Current affairs and politics focussed on the US'
    INDEX = 'http://www.theatlantic.com/doc/current'
    language = 'en'

    remove_tags_before = dict(name='div', id='storytop')
    remove_tags        = [
                        dict(name='div', id=['seealso','storybottom',  'footer', 'ad_banner_top', 'sidebar','articletoolstop','subcontent',]),
                        dict(name='p', attrs={'id':["pagination"]}),
                        dict(name='table',attrs={'class':"tools"}),
                        dict(name='a', href='/a/newsletters.mhtml')
                         ]
    no_stylesheets     = True

    extra_css = '''
                    #timestamp{font-family:Arial,Helvetica,sans-serif; color:#666666 ;font-size:x-small}
                    #storytype{font-family:Arial,Helvetica,sans-serif; color:#D52B1E ;font-weight:bold; font-size:x-small}
                    h2{font-family:georgia,serif; font-style:italic;font-size:x-small;font-weight:normal;}
                    h1{font-family:georgia,serif; font-weight:bold; font-size:large}
                    #byline{font-family:georgia,serif; font-weight:bold; font-size:x-small}
                    #topgraf{font-family:Arial,Helvetica,sans-serif;font-size:x-small;font-weight:bold;}
                    .artsans{{font-family:Arial,Helvetica,sans-serif;font-size:x-small;}
                '''
    def parse_index(self):
        articles = []

        soup = self.index_to_soup(self.INDEX)

        issue = soup.find('span', attrs={'class':'issue'})
        if issue:
            self.timefmt = ' [%s]'%self.tag_to_string(issue).rpartition('|')[-1].strip().replace('/', '-')

        cover = soup.find('img', alt=re.compile('Cover'), src=True)
        if cover is not None:
            self.cover_url = 'http://theatlantic.com'+cover['src']

        for item in soup.findAll('div', attrs={'class':'item'}):
            a = item.find('a')
            if a and a.has_key('href'):
                url = a['href']#.replace('/doc', 'doc/print')
                if not url.startswith('http://'):
                    url = 'http://www.theatlantic.com/'+url
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
