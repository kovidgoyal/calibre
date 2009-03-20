#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
nacional.hr
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class NacionalCro(BasicNewsRecipe):
    title                 = 'Nacional - Hr'
    __author__            = 'Darko Miletic'
    description           = "news from Croatia"
    publisher             = 'Nacional.hr'
    category              = 'news, politics, Croatia'    
    oldest_article        = 2
    max_articles_per_feed = 100
    delay                 = 4
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    remove_javascript     = True    
    language              = _('Croatian')

    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    remove_tags = [dict(name=['object','link','embed'])]
    
    feeds = [(u'Najnovije Vijesti', u'http://www.nacional.hr/rss')]

    def preprocess_html(self, soup):
        soup.html['lang']     = 'hr-HR'
        mtag = '<meta http-equiv="Content-Language" content="hr-HR"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    def print_version(self, url):
        rest, sep, disc = url.rpartition('/')
        return rest.replace('/clanak/','/clanak/print/')
        