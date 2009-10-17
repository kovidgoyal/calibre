#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.azstarnet.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Azstarnet(BasicNewsRecipe):
    title                 = 'Arizona  Daily Star'
    __author__            = 'Darko Miletic'
    description           = 'news from Arizona'
    language = 'en'

    publisher             = 'azstarnet.com'
    category              = 'news, politics, Arizona, USA'
    delay                 = 1
    oldest_article        = 1
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    needs_subscription    = True
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open('http://azstarnet.com/registration/retro.php')
            br.select_form(nr=1)
            br['email'] = self.username
            br['pass' ] = self.password
            br.submit()
        return br


    keep_only_tags = [dict(name='div', attrs={'id':'storycontent'})]

    remove_tags = [
                     dict(name=['object','link','iframe','base','img'])
                    ,dict(name='div',attrs={'class':'bannerinstory'})
                  ]


    feeds = [(u'Tucson Region', u'http://rss.azstarnet.com/index.php?site=metro')]

    def preprocess_html(self, soup):
        soup.html['dir' ] = 'ltr'
        soup.html['lang'] = 'en-US'
        mtag = '\n<meta http-equiv="Content-Language" content="en-US"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

