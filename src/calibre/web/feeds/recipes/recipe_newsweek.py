#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re, string, time
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class Newsweek(BasicNewsRecipe):

    title          = 'Newsweek'
    __author__     = 'Kovid Goyal'
    description    = 'Weekly news and current affairs in the US'
    no_stylesheets = True
    
    extra_css = '#content { font:serif 12pt; }\n.story {font:12pt}\n.HorizontalHeader {font:18pt}\n.deck {font:16pt}'
    keep_only_tags = [dict(name='div', id='content')]

    remove_tags = [
        dict(name=['script',  'noscript']),
        dict(name='div',  attrs={'class':['ad', 'SocialLinks', 'SocialLinksDiv',
                                          'channel', 'bot', 'nav', 'top', 
                                          'EmailArticleBlock', 
                                          'comments-and-social-links-wrapper',
                                          'inline-social-links-wrapper',
                                          'inline-social-links',
                                          ]}),
        dict(name='div',  attrs={'class':re.compile('box')}),
        dict(id=['ToolBox', 'EmailMain', 'EmailArticle', 'comment-box',
                 'nw-comments'])
    ]
    
    recursions = 1
    match_regexps = [r'http://www.newsweek.com/id/\S+/page/\d+']
    
    
    def get_sections(self, soup):
        sections = []
        
        def process_section(img):
            articles = []
            match = re.search(r'label_([^_.]+)', img['src'])
            if match is None:
                return
            title =  match.group(1)
            if title in ['coverstory', 'more', 'tipsheet']:
                return
            title = string.capwords(title)
            
            for a in img.parent.findAll('a', href=True):
                art, href = a.string, a['href']
                if not re.search('\d+$', href) or not art or 'Preview Article' in art:
                    continue
                articles.append({
                                 'title':art, 'url':href, 'description':'', 
                                 'content':'', 'date':'' 
                    })
            sections.append((title, articles))
                
            img.parent.extract()

        for img in soup.findAll(src=re.compile('/label_')):
            process_section(img)
            
        return sections

    
    def parse_index(self):
        ci = self.get_current_issue()
        if not ci:
            raise RuntimeError('Unable to connect to newsweek.com. Try again later.')
        soup = self.index_to_soup(ci)
        img = soup.find(alt='Cover')
        if img is not None and img.has_key('src'):
            small = img['src']
            match = re.search(r'(\d+)_', small.rpartition('/')[-1])
            if match is not None:
                self.timefmt = strftime(' [%d %b, %Y]', time.strptime(match.group(1), '%y%m%d'))
            self.cover_url = small.replace('coversmall', 'coverlarge')
            
        sections = self.get_sections(soup)
        sections.insert(0, ('Main articles', []))
        
        for tag in soup.findAll('h5'):
            a = tag.find('a', href=True)
            if a is not None:
                title = self.tag_to_string(a)
                if not title:
                    a = 'Untitled article'
                art = {
                       'title' : title,
                       'url'   : a['href'],
                       'description':'', 'content':'',
                       'date': strftime('%a, %d %b')
                       }
                if art['title'] and art['url']:
                    sections[0][1].append(art)
        return sections
        
    
    def postprocess_html(self, soup, first_fetch):
        divs = list(soup.findAll('div', 'pagination'))
        if not divs:
            return
        divs[0].extract()
        if len(divs) > 1:
            soup.find('body')['style'] = 'page-break-after:avoid'
            divs[1].extract()            
            
            h1 = soup.find('h1')
            if h1:
                h1.extract()
            ai = soup.find('div', 'articleInfo')
            ai.extract()
        else:
            soup.find('body')['style'] = 'page-break-before:always; page-break-after:avoid;'
        return soup
    
    def get_current_issue(self):
        from urllib2 import urlopen # For some reason mechanize fails
        home = urlopen('http://www.newsweek.com').read() 
        soup = BeautifulSoup(home)
        img  = soup.find('img', alt='Current Magazine')
        if img and img.parent.has_key('href'):
            return urlopen(img.parent['href']).read()
    
