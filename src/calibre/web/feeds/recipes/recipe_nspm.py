#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
nspm.rs
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Nspm(BasicNewsRecipe):
    title                 = 'Nova srpska politicka misao'
    __author__            = 'Darko Miletic'
    description           = 'Casopis za politicku teoriju i drustvena istrazivanja'    
    publisher             = 'NSPM'
    category              = 'news, politics, Serbia'    
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    INDEX                 = 'http://www.nspm.rs/?alphabet=l'
    encoding              = 'utf8'
    remove_javascript     = True
    language              = _('Serbian')
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    remove_tags        = [
                            dict(name=['link','object','embed'])
                           ,dict(name='td', attrs={'class':'buttonheading'})
                         ]
    
    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.INDEX)
        return br

    feeds = [(u'Nova srpska politicka misao', u'http://www.nspm.rs/feed/rss.html')]

    def print_version(self, url):
        return url.replace('.html','/stampa.html')

    def cleanup_image_tags(self,soup):
        for item in soup.findAll('img'):
            for attrib in ['height','width','border','align']:
                if item.has_key(attrib):
                   del item[attrib]
            oldParent = item.parent
            myIndex = oldParent.contents.index(item)
            item.extract()
            divtag = Tag(soup,'div')
            brtag  = Tag(soup,'br')
            oldParent.insert(myIndex,divtag)
            divtag.append(item)
            divtag.append(brtag)
        return soup

    def preprocess_html(self, soup):
        lng = 'sr-Latn-RS'
        soup.html['xml:lang'] = lng
        soup.html['lang']     = lng
        ftag = soup.find('meta',attrs={'http-equiv':'Content-Language'})
        if ftag:
           ftag['content'] = lng
        for item in soup.findAll(style=True):
            del item['style']     
        return self.cleanup_image_tags(soup)
