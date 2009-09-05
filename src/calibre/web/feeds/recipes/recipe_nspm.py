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
    encoding              = 'utf-8'
    language = 'sr'

    lang                  = 'sr-Latn-RS'
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{text-align: justify; font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    conversion_options = {
                          'comment'          : description
                        , 'tags'             : category
                        , 'publisher'        : publisher
                        , 'language'         : lang
                        , 'pretty_print'     : True
                        }

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

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
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
        return self.adeify_images(soup)
