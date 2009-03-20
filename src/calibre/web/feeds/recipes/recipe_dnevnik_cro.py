#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
dnevnik.hr
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class DnevnikCro(BasicNewsRecipe):
    title                 = 'Dnevnik - Hr'
    __author__            = 'Darko Miletic'
    description           = "Vijesti iz Hrvatske"
    publisher             = 'Dnevnik.hr'
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
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 
     
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags     = [dict(name='div', attrs={'id':'article'})]
        
    remove_tags = [
                    dict(name=['object','link','embed'])
                   ,dict(name='div', attrs={'class':'menu'})
                   ,dict(name='div', attrs={'id':'video'})
                  ]

    remove_tags_after  = dict(name='div', attrs={'id':'content'})

    feeds = [(u'Vijesti', u'http://rss.dnevnik.hr/index.rss')]

    def preprocess_html(self, soup):
        soup.html['lang']     = 'hr-HR'
        mtag = '<meta http-equiv="Content-Language" content="hr-HR"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

