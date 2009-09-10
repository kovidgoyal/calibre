#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
vreme.com
'''

import re
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class Vreme(BasicNewsRecipe):
    title                = 'Vreme'
    __author__           = 'Darko Miletic'
    description          = 'Politicki Nedeljnik Srbije'
    publisher            = 'NP Vreme d.o.o.'
    category             = 'news, politics, Serbia'
    delay                = 1
    no_stylesheets       = True
    needs_subscription   = True
    INDEX                = 'http://www.vreme.com'
    LOGIN                = 'http://www.vreme.com/account/login.php?url=%2F'
    use_embedded_content = False
    encoding             = 'utf-8'
    language = 'sr'

    lang                 = 'sr-Latn-RS'
    direction            = 'ltr'
    extra_css            = ' @font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} .heading1{font-family: sans1, sans-serif; font-size: x-large; font-weight: bold} .heading2{font-family: sans1, sans-serif; font-size: large; font-weight: bold} .toc-heading{font-family: sans1, sans-serif; font-size: small} .column-heading2{font-family: sans1, sans-serif; font-size: large} .column-heading1{font-family: sans1, sans-serif; font-size: x-large} .column-normal{font-family: sans1, sans-serif; font-size: medium} .large{font-family: sans1, sans-serif; font-size: large} '

    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }


    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open(self.LOGIN)
            br.select_form(name='f')
            br['username'] = self.username
            br['password'] = self.password
            br.submit()
        return br

    def parse_index(self):
        articles = []
        soup = self.index_to_soup(self.INDEX)

        for item in soup.findAll(['h3','h4']):
            description = ''
            title_prefix = ''
            feed_link = item.find('a')
            if feed_link and feed_link.has_key('href') and feed_link['href'].startswith('/cms/view.php'):
                url   = self.INDEX + feed_link['href']
                title = title_prefix + self.tag_to_string(feed_link)
                date  = strftime(self.timefmt)
                articles.append({
                                  'title'      :title
                                 ,'date'       :date
                                 ,'url'        :url
                                 ,'description':description
                                })
        return [(soup.head.title.string, articles)]

    remove_tags = [
                    dict(name=['object','link'])
                   ,dict(name='table',attrs={'xclass':'image'})
                  ]

    def print_version(self, url):
        return url + '&print=yes'

    def preprocess_html(self, soup):
        del soup.body['text'   ]
        del soup.body['bgcolor']
        del soup.body['onload' ]
        soup.html['lang'] = self.lang
        soup.html['dir' ] = self.direction

        attribs = [  'style','font','valign'
                    ,'colspan','width','height'
                    ,'rowspan','summary','align'
                    ,'cellspacing','cellpadding'
                    ,'frames','rules','border'
                  ]
        for item in soup.body.findAll(name=['table','td','tr','th','caption','thead','tfoot','tbody','colgroup','col']):
            item.name = 'div'
            for attrib in attribs:
                if item.has_key(attrib):
                   del item[attrib]

        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return soup

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.INDEX)
        cover_item = soup.find('div',attrs={'id':'najava'})
        if cover_item:
           cover_url = self.INDEX + cover_item.img['src']
        return cover_url
