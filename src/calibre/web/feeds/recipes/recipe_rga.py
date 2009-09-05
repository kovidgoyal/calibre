#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, W. Gerard <wii at gerard-nrw.de>'
'''
rga-online.de
'''

from calibre.web.feeds.news import BasicNewsRecipe

class rga_onliner(BasicNewsRecipe):
    title                 = 'RGA Online - German'
    __author__            = 'Werner Gerard'
    description           = "E-Zeitung aus RSS-Artikeln zusammengestellt."
    publisher             = 'RGA-Online'
    category              = 'Nachrichten, RGA'
    oldest_article        = 3
    max_articles_per_feed = 100
    language = 'de'

    lang                  = 'de-DE'
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'

    remove_tags_before = dict(name='span', attrs={'class':'headgross'})
    remove_tags_after    = dict(name='br', attrs={'clear':'all'})

#    remove_tags_after    = dict(name='br', attrs={'clear':'clear'})

    feeds        = [
                            ('RGA-Online Remscheid', 'http://www.rga-online.de/rss/rs_news.php'),
                            ('RGA-Online Wermelskirchen', 'http://www.rga-online.de/rss/wk_news.php'),
                            ('RGA-Online Hueckeswagen', 'http://www.rga-online.de/rss/hk_news.php'),
                            ('RGA-Online Radevormwald', 'http://www.rga-online.de/rss/rz_news.php'),
                            ('RGA-Online Tagesthemen', 'http://www.rga-online.de/rss/tt_news.php'),
                            ('RGA-Online Brennpunkte', 'http://www.rga-online.de/rss/br_news.php'),
                            ('RGA-Online Sport', 'http://www.rga-online.de/rss/spo_news.php'),
                            ('RGA-Online Lokalsport', 'http://www.rga-online.de/rss/sp_news.php'),
                            ('RGA-Online Bergisches Land', 'http://www.rga-online.de/rss/bg_news.php'),
                            ('RGA-Online Bergische Wirtschaft', 'http://www.rga-online.de/rss/bw_news.php')
                          ]
#"print based version"
#    def print_version(self, url):
#         main, separatior, sub = url.rpartition('?')
#          sub1, sep1, artikel = sub.rpartition('&')
#          sub2, sep2, publikation = sub1.rpartition('&')


#          return 'http://www.pipeline.de/cgi-bin/pipeline.fcg?userid=1&publikation=2&template=druck.html&'+ publikation + '&' + artikel
#          return 'http://www.pipeline.de/cgi-bin/pipeline.fcg?userid=1&publikation=2&template=druck.html&redaktion=2&artikel=109208787'
#                     http://www.pipeline.de/cgi-bin/pipeline.fcg?userid=1&publikation=2&template=druck.html&redaktion=1&artikel=109209772
#     http://www.rga-online.de/lokales/h6ckeswagen.php?publikation=2&template=phparttext&ausgabe=49740&redaktion=2&artikel=109208787


    def get_cover_url(self):
         return 'http://rga.werner-gerard.de/rga.jpg'

    def postprocess_html(self, soup, first):
        for tag in soup.findAll(name=['table', 'tr', 'td']):
            tag.name = 'span'
        return soup
