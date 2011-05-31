#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class KellogFaculty(BasicNewsRecipe):

    title          = 'Kellog Faculty Blogs'
    __author__     = 'Kovid Goyal'
    description    = 'Blogs of the Kellog School of Management Faculty'
    no_stylesheets = True
    encoding       = 'utf-8'
    language = 'en'

    remove_tags_before = {'name':'h2'}
    remove_tags_after = {'class':'col-two-text'}

    def parse_index(self):
        soup = self.index_to_soup('http://www.kellogg.northwestern.edu/Faculty/Blogroll.aspx')
        feeds, articles = [], []
        feed_title = None
        main = soup.find(id='bodyCopy')
        for tag in main.findAll(['h3', 'div']):
            if tag.name == 'h3':
                title = self.tag_to_string(tag).capitalize()
                a = tag.find('a', href=True)
                if articles and feed_title:
                    feeds.append((feed_title, articles))
                articles = []
                # Keep only blogs hosted on the Kellog servers
                feed_title = title if a and 'insight.kellog' in a['href'] else None
            elif tag.name == 'div' and tag.get('class', '') == 'rssfeed':
                script = tag.find('script', src=True)
                text = \
                self.browser.open(script['src']).read().replace('document.write(',
                        '')[:-2]
                text = eval(text)
                asoup = BeautifulSoup(text)
                for tag in asoup.findAll('div',
                        attrs={'class':'rssincl-entry'}):
                    title = self.tag_to_string(tag.find(attrs={'class':'rssincl-itemtitle'}))
                    try:
                        desc = self.tag_to_string(tag.find(attrs={'class':'rssincl-itemdesc'}))
                    except:
                        desc = ''
                    url = tag.find('a', href=True)['href']

                    articles.append({
                        'title':title.strip(), 'url':url, 'description':desc.strip(), 'date':''
                        })

        return feeds

    def postprocess_html(self, soup, first_fetch):
        for tag in soup.findAll(style=True):
            del tag['style']
        head = soup.find('head')
        if head is not None:
            for p in head.findAll('p'): p.extract()
        for meta in soup.findAll('meta', attrs={'name':'description'}): meta.extract()
        for t in head.findAll(text=True): t.extract()
        return soup


