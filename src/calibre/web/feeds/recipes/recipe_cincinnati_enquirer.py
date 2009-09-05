#!/usr/bin/env python
__license__   = 'GPL v3'
__copyright__ = '2009 Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.web.feeds.news import BasicNewsRecipe

class AdvancedUserRecipe1234144423(BasicNewsRecipe):
    title          = u'Cincinnati Enquirer'
    oldest_article = 7
    language = 'en'

    __author__     = 'Joseph Kitzmiller'
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding = 'cp1252'
    extra_css = ' p {font-size: medium; font-weight: normal;} '
    
    keep_only_tags = [dict(name='div', attrs={'class':'padding'})]
    
    remove_tags = [
                     dict(name=['object','link','table','embed'])
                    ,dict(name='div',attrs={'id':'pluckcomments'})
                    ,dict(name='div',attrs={'class':'articleflex-container'})
                  ]
   
    feeds          = [(u'Cincinnati Enquirer', u'http://rss.cincinnati.com/apps/pbcs.dll/section?category=rssenq01&mime=xml')]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        for item in soup.findAll(face=True):
            del item['face']
        return soup
