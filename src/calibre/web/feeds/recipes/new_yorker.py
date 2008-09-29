#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

import re
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import NavigableString

class NewYorker(BasicNewsRecipe):
    
    title       = 'The New Yorker'
    __author__  = 'Kovid Goyal'
    description = 'News and opinion'
    
    remove_tags = [
                   dict(name='div', id=['printoptions', 'header', 'articleBottom']),
                   dict(name='div', attrs={'class':['utils', 'icons']})
                   ]
    
    
    def parse_index(self):
        toc_pat = re.compile(r'/magazine/toc/\d+/\d+/\d+/toc_\d+')
        soup = self.soup(self.browser.open('http://www.newyorker.com/').read())
        a = soup.find('a', href=toc_pat)
        if a is None:
            raise Exception('Could not find the current issue of The New Yorker')
        href = a['href']
        href = 'http://www.newyorker.com'+href[href.index('/magazine'):]
        soup = self.soup(self.browser.open(href).read())
        img = soup.find(id='inThisIssuePhoto')
        if img is not None:
            self.cover_url = 'http://www.newyorker.com'+img['src']
            alt = img.get('alt', None)
            if alt:
                self.timefmt = ' [%s]'%alt
        features = soup.findAll(attrs={'class':re.compile('feature')})
        
        category, sections, articles = None, [], []
        for feature in features:
            head = feature.find('img', alt=True, attrs={'class':'featurehed'})
            if head is None:
                continue
            if articles:
                sections.append((category, articles))
            category, articles = head['alt'], []
            if category in ('', 'AUDIO', 'VIDEO', 'BLOGS', 'GOINGS ON'):
                continue
            
            for a in feature.findAll('a', href=True):
                href = 'http://www.newyorker.com'+a['href']+'?printable=true'
                title, in_title, desc = '', True, ''
                for tag in a.contents:
                    if getattr(tag, 'name', None) == 'br':
                        in_title = False
                        continue
                    if isinstance(tag, NavigableString):
                        text = unicode(tag)
                        if in_title:
                            title += text
                        else:
                            desc += text
                if title and not 'Audio:' in title:
                    art = {
                           'title': title,
                           'desc': desc, 'content':'',
                           'url': href,
                           'date': strftime('%a, %d %b'),
                           }
                    articles.append(art)
                
#        from IPython.Shell import IPShellEmbed
#        ipshell = IPShellEmbed()
#        ipshell()
#        raise Exception()

        return sections