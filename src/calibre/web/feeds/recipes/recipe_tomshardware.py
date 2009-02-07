#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
tomshardware.com
'''

from calibre.web.feeds.recipes import BasicNewsRecipe

class Tomshardware(BasicNewsRecipe):
    
    title       = "Tom's Hardware US"
    __author__  = 'Darko Miletic'
    description = 'Hardware reviews and News'
    no_stylesheets = True
    needs_subscription = True
    language = _('English')
    INDEX = 'http://www.tomshardware.com'
    LOGIN = 'http://www.tomshardware.com/membres/?r=%2Fus%2F#loginForm'
    cover_url = 'http://img.bestofmedia.com/img/tomshardware/design/tomshardware.jpg'
    
    html2lrf_options = [  '--comment'       , description
                        , '--category'      , 'hardware,news'
                        , '--base-font-size', '10'
                       ]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open(self.LOGIN)
            br.select_form(name='connexion')
            br['login'] = self.username
            br['mdp'  ] = self.password
            br.submit()
        return br

    remove_tags = [
                     dict(name='div' , attrs={'id':'header' })
                    ,dict(name='object')
                  ]
    
    feeds = [
              (u'Latest Articles', u'http://www.tomshardware.com/feeds/atom/tom-s-hardware-us,18-2.xml')
             ,(u'Latest News'    , u'http://www.tomshardware.com/feeds/atom/tom-s-hardware-us,18-1.xml')
            ]
                  
    def print_version(self, url):
        main, sep, rest = url.rpartition('.html')
        rmain, rsep, article_id = main.rpartition(',')
        tmain, tsep, trest = rmain.rpartition('/reviews/')
        if tsep:
            return 'http://www.tomshardware.com/review_print.php?p1=' + article_id
        return 'http://www.tomshardware.com/news_print.php?p1=' + article_id        

    def preprocess_html(self, soup):
        del(soup.body['onload'])
        return soup
