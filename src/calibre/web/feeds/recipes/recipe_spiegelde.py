#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
spiegel.de
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Spiegel_ger(BasicNewsRecipe):
    title                 = 'Spiegel Online - German'
    __author__            = 'Darko Miletic'
    description           = "Immer die neueste Meldung auf dem Schirm, sekundenaktuell und uebersichtlich: Mit dem RSS-Angebot von SPIEGEL ONLINE entgeht Ihnen keine wichtige Meldung mehr, selbst wenn Sie keinen Internet-Browser geoeffnet haben. Sie koennen unsere Nachrichten-Feeds ganz einfach abonnieren - unkompliziert, kostenlos und nach Ihren persoenlichen Themen-Vorlieben."
    publisher             = 'SPIEGEL ONLINE Gmbh'
    category              = 'SPIEGEL ONLINE, DER SPIEGEL, Nachrichten, News,Dienste, RSS, RSS, Feedreader, Newsfeed, iGoogle, Netvibes, Widget'    
    oldest_article        = 7
    max_articles_per_feed = 100
    language = 'de'

    lang                  = 'de-DE'
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
                        
    keep_only_tags = [dict(name='div', attrs={'id':'spMainContent'})]

    remove_tags = [dict(name=['object','link','base'])]
    
    remove_tags_after = dict(name='div', attrs={'id':'spArticleBody'})

    feeds          = [(u'Spiegel Online', u'http://www.spiegel.de/schlagzeilen/index.rss')]

    def print_version(self, url):
        main, sep, rest = url.rpartition(',')
        rmain, rsep, rrest = main.rpartition(',')
        return rmain + ',druck-' + rrest + ',' + rest

    def preprocess_html(self, soup):
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        htmltag = soup.find('html')
        if not htmltag:
            thtml = Tag(soup,'html',[("lang",self.lang),("xml:lang",self.lang),("dir","ltr")])
            soup.insert(0,thtml)
            thead = soup.head
            tbody = soup.body
            thead.extract()
            tbody.extract()
            soup.html.insert(0,tbody)
            soup.html.insert(0,thead)
        return soup
