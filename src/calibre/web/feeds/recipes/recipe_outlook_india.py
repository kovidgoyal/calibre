#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from calibre.web.feeds.news import BasicNewsRecipe

class OutlookIndia(BasicNewsRecipe):

    title          = 'Outlook India'
    __author__     = 'Kovid Goyal and Sujata Raman'
    description    = 'Weekly news and current affairs in India'
    no_stylesheets = True
    encoding       = 'utf-8'
    language = _('English')
    keep_only_tags = [
                      dict(name='div', attrs={'id':["ctl00_cphpagemiddle_reparticle_ctl00_divfullstorytext","ctl00_cphpagemiddle_reparticle_ctl00_divartpic","ctl00_cphpagemiddle_reparticle_ctl00_divfspheading", "ctl00_cphpagemiddle_reparticle_ctl00_divartpiccaption",  "ctl00_cphpagemiddle_reparticle_ctl00_divartpiccredit","ctl00_cphpagemiddle_reparticle_ctl00_divfspintro", "ctl00_cphpagemiddle_reparticle_ctl00_divartbyline", ]}),
                           ]
    remove_tags = [dict(name=['script','object'])]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser(self)
        # This site sends article titles in the cookie which occasionally
        # contain non ascii characters causing httplib to fail. Instead just
        # disable cookies as they're not needed for download. Proper solution
        # would be to implement a unicode aware cookie jar
        br.set_cookiejar(None)
        return br


    def parse_index(self):


        soup = self.index_to_soup('http://www.outlookindia.com/issues.aspx')
# find cover pic
        div = soup.find('div', attrs={'class':re.compile('cententcellpadding')})

        if div is None: return None
        a = div.find('a')

        if a is not None:
            href =  'http://www.outlookindia.com/' + a['href']

        soup = self.index_to_soup(href)
        cover = soup.find('img', attrs={'id':"ctl00_cphpagemiddle_dlissues_ctl00_imgcoverpic"}, src=True)
        if cover is not None:

            self.cover_url = cover['src']

 # end find cover pic

        div = soup.find('table', attrs={'id':re.compile('ctl00_cphpagemiddle_dlissues')})

        if div is None: return None
        a = div.find('a')

        if a is not None:
            href =  'http://www.outlookindia.com/' + a['href']

        soup = self.index_to_soup(href)

        articles = []

        for a in soup.findAll('a', attrs={'class':'contentpgsubheadinglink'}):

            if a and a.has_key('href'):
                url = 'http://www.outlookindia.com/' + a['href']
            else:
                url =''
            title = self.tag_to_string(a)

            date = ''
            description = ''
            articles.append({
                                 'title':title,
                                 'date':date,
                                 'url':url,
                                 'description':description
                                })

        return [('Current Issue', articles)]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return self.adeify_images(soup)

    def postrocess_html(self, soup, first):

            for tag in soup.findAll(name=['table', 'tr', 'td','tbody']):
                tag.name = 'div'


            return soup

