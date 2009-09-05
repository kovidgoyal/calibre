#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
nspm.rs/nspm-in-english
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Nspm_int(BasicNewsRecipe):
    title                 = 'NSPM in English'
    __author__            = 'Darko Miletic'
    description           = 'Magazine dedicated to political theory and sociological research'        
    oldest_article        = 20
    max_articles_per_feed = 100
    language = 'en'

    no_stylesheets        = True
    use_embedded_content  = False
    INDEX                 = 'http://www.nspm.rs/?alphabet=l'
    cover_url = 'http://nspm.rs/templates/jsn_epic_pro/images/logol.jpg'
    html2lrf_options = [
                          '--comment', description
                        , '--base-font-size', '10'
                        , '--category', 'news, politics, Serbia, english'
                        , '--publisher', 'IIC NSPM'
                        ]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        br.open(self.INDEX)
        return br


    keep_only_tags = [dict(name='div', attrs={'id':'jsn-mainbody'})]
    remove_tags    = [dict(name='div', attrs={'id':'yvComment'   })]

    feeds = [ (u'NSPM in English', u'http://nspm.rs/nspm-in-english/feed/rss.html')]
