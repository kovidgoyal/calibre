#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
'''
time.com
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class Time(BasicNewsRecipe):
    title                 = u'Time'
    __author__            = 'Kovid Goyal and Sujata Raman'
    description           = 'Weekly magazine'
    encoding = 'utf-8'
    no_stylesheets        = True
    language = 'en'

    extra_css      = '''.headline {font-size: large;}
    .fact { padding-top: 10pt  }
    h1 {font-family:Arial,Sans-serif}
    .byline{font-family:Arial,Sans-serif; font-size:xx-small ;color:blue}
    .timestamp{font-family:Arial,Sans-serif; font-size:x-small ;color:gray}'''
    remove_tags_before = dict(id="artHd")
    remove_tags_after = {'class':"ltCol"}
    remove_tags    = [
            {'class':['articleTools', 'enlarge', 'search','socialtools','blogtools','moretools','page','nextUp','next','subnav','RSS','line2','first','ybuzz','articlePagination','chiclets','imgcont','createListLink','rlinks','tabsWrap','pagination']},
            {'id':['quigoArticle', 'contentTools', 'articleSideBar', 'header', 'navTop','articleTools','feedmodule','feedmodule3','promos','footer','linksFooter','timeArchive','belt','relatedStories','packages','Features']},
            {'target':'_blank'},
                      ]
    recursions = 1
    match_regexps = [r'/[0-9,]+-(2|3|4|5|6|7|8|9)(,\d+){0,1}.html']


    def parse_index(self):
        soup = self.index_to_soup('http://www.time.com/time/magazine')
        img = soup.find('a', title="View Large Cover", href=True)
        if img is not None:
            cover_url = 'http://www.time.com'+img['href']
            try:
                nsoup = self.index_to_soup(cover_url)
                img = nsoup.find('img', src=re.compile('archive/covers'))
                if img is not None:
                    self.cover_url = img['src']
            except:
                self.log.exception('Failed to fetch cover')


        feeds = []
        parent = soup.find(id='tocGuts')
        for seched in parent.findAll(attrs={'class':'toc_seched'}):
            section = self.tag_to_string(seched).capitalize()
            articles = list(self.find_articles(seched))
            feeds.append((section, articles))

        return feeds

    def find_articles(self, seched):
        for a in seched.findNextSiblings('a', href=True, attrs={'class':'toc_hed'}):
            yield {
                    'title' : self.tag_to_string(a),
                    'url'   : 'http://www.time.com'+a['href'],
                    'date'  : '',
                    'description' : self.article_description(a)
                    }

    def article_description(self, a):
        ans = []
        while True:
            t = a.nextSibling
            if t is None:
                break
            a = t
            if getattr(t, 'name', False):
                if t.get('class', '') == 'toc_parens' or t.name == 'br':
                    continue
                if t.name in ('div', 'a'):
                    break
                ans.append(self.tag_to_string(t))
            else:
                ans.append(unicode(t))
        return u' '.join(ans).replace(u'\xa0', u'').strip()

    def postprocess_html(self, soup, first_page):
        div = soup.find(attrs={'class':'artPag'})
        if div is not None:
            div.extract()
        if not first_page:
            for cls in ('photoBkt', 'artHd'):
                div = soup.find(attrs={'class':cls})
                if div is not None:
                    div.extract()
            div = soup.find(attrs={'class':'artTxt'})
            if div is not None:
                p = div.find('p')
                if p is not None:
                    p.extract()

        return soup
