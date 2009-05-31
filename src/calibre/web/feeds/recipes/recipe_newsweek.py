#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class Newsweek(BasicNewsRecipe):

    title          = 'Newsweek'
    __author__     = 'Kovid Goyal'
    description    = 'Weekly news and current affairs in the US'
    no_stylesheets = True
    encoding       = 'utf-8'
    language = _('English')
    remove_tags = [
            {'class':['navbar', 'ad', 'sponsorLinksArticle', 'mm-content',
                'inline-social-links-wrapper', 'email-article',
                'comments-and-social-links-wrapper', 'EmailArticleBlock']},
            {'id' : ['footer', 'ticker-data', 'topTenVertical',
                'digg-top-five', 'mesothorax', 'nw-comments',
                'ToolBox', 'EmailMain']},
            {'class': re.compile('related-cloud')},
            ]
    keep_only_tags = [{'class':['article HorizontalHeader', 'articlecontent']}]


    recursions = 1
    match_regexps = [r'http://www.newsweek.com/id/\S+/page/\d+']

    def find_title(self, section):
        d = {'scope':'Scope', 'thetake':'The Take', 'features':'Features',
                None:'Departments', 'culture':'Culture'}
        ans = None
        a = section.find('a', attrs={'name':True})
        if a is not None:
            ans = a['name']
        return d.get(ans, ans)


    def find_articles(self, section):
        ans = []
        for x in section.findAll('h5'):
            title = ' '.join(x.findAll(text=True)).strip()
            a = x.find('a')
            if not a: continue
            href = a['href']
            ans.append({'title':title, 'url':href, 'description':'', 'date': strftime('%a, %d %b')})
        if not ans:
            for x in section.findAll('div', attrs={'class':'hdlItem'}):
                a = x.find('a', href=True)
                if not a : continue
                title = ' '.join(a.findAll(text=True)).strip()
                href = a['href']
                if 'http://xtra.newsweek.com' in href: continue
                ans.append({'title':title, 'url':href, 'description':'', 'date': strftime('%a, %d %b')})

        #for x in ans:
        #    x['url'] += '/output/print'
        return ans


    def parse_index(self):
        soup = self.get_current_issue()
        if not soup:
            raise RuntimeError('Unable to connect to newsweek.com. Try again later.')
        sections = soup.findAll('div', attrs={'class':'featurewell'})
        titles = map(self.find_title, sections)
        articles = map(self.find_articles, sections)
        ans = list(zip(titles, articles))
        def fcmp(x, y):
            tx, ty = x[0], y[0]
            if tx == "Features": return cmp(1, 2)
            if ty == "Features": return cmp(2, 1)
            return cmp(tx, ty)
        return sorted(ans, cmp=fcmp)

    def postprocess_html(self, soup, first_fetch):
        if not first_fetch:
            h1 = soup.find(id='headline')
            if h1:
                h1.extract()
            div = soup.find(attrs={'class':'articleInfo'})
            if div:
                div.extract()
        divs = list(soup.findAll('div', 'pagination'))
        if not divs:
            return soup
        for div in divs[1:]: div.extract()
        all_a = divs[0].findAll('a', href=True)
        divs[0]['style']="display:none"
        if len(all_a) > 1:
            all_a[-1].extract()
        test = re.compile(self.match_regexps[0])
        for a in soup.findAll('a', href=test):
            if a not in all_a:
                del a['href']
        return soup

    def get_current_issue(self):
        soup = self.index_to_soup('http://www.newsweek.com')
        div = soup.find('div', attrs={'class':re.compile('more-from-mag')})
        if div is None: return None
        a = div.find('a')
        if a is not None:
            href = a['href'].split('#')[0]
            return self.index_to_soup(href)

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup('http://www.newsweek.com')
        link_item = soup.find('div',attrs={'class':'cover-image'})
        if link_item and link_item.a and link_item.a.img:
           cover_url = link_item.a.img['src']
        return cover_url


