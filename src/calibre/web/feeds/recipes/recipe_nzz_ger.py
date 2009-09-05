#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
www.nzz.ch
'''

from calibre.web.feeds.recipes import BasicNewsRecipe

class Nzz(BasicNewsRecipe):
    title                 = 'NZZ Online'
    __author__            = 'Darko Miletic'
    description           = 'Laufend aktualisierte Nachrichten, Analysen und Hintergruende zu Politik, Wirtschaft, Kultur und Sport'
    publisher             = 'NZZ AG'
    category              = 'news, politics, nachrichten, Switzerland'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    lang                  = 'de-CH'
    language = 'de'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"'

    keep_only_tags = [dict(name='div', attrs={'class':'article'})]

    remove_tags = [
                     dict(name=['object','link','base','script'])
                    ,dict(name='div',attrs={'class':['more','teaser','advXertXoriXals','legal']})
                    ,dict(name='div',attrs={'id':['popup-src','readercomments','google-ad','advXertXoriXals']})
                  ]

    feeds = [
               (u'Neuste Artikel', u'http://www.nzz.ch/feeds/recent/'                     )
              ,(u'International' , u'http://www.nzz.ch/nachrichten/international?rss=true')
              ,(u'Schweiz'       , u'http://www.nzz.ch/nachrichten/schweiz?rss=true')
              ,(u'Wirtschaft'    , u'http://www.nzz.ch/nachrichten/wirtschaft/aktuell?rss=true')
              ,(u'Finanzmaerkte' , u'http://www.nzz.ch/finanzen/nachrichten?rss=true')
              ,(u'Zuerich'       , u'http://www.nzz.ch/nachrichten/zuerich?rss=true')
              ,(u'Sport'         , u'http://www.nzz.ch/nachrichten/sport?rss=true')
              ,(u'Panorama'      , u'http://www.nzz.ch/nachrichten/panorama?rss=true')
              ,(u'Kultur'        , u'http://www.nzz.ch/nachrichten/kultur/aktuell?rss=true')
              ,(u'Wissenschaft'  , u'http://www.nzz.ch/nachrichten/wissenschaft?rss=true')
              ,(u'Medien'        , u'http://www.nzz.ch/nachrichten/medien?rss=true')
              ,(u'Reisen'        , u'http://www.nzz.ch/magazin/reisen?rss=true')
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
        soup.head.insert(0,mtag)
        return soup

    def print_version(self, url):
        return url + '?printview=true'

