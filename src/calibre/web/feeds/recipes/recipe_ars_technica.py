#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
arstechnica.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class ArsTechnica2(BasicNewsRecipe):
    title                 = u'Ars Technica'
    language              = _('English')
    __author__            = 'Darko Miletic and Sujata Raman'
    description           = 'The art of technology'
    publisher             = 'Ars Technica'
    category              = 'news, IT, technology'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf8'
    remove_javascript     = True
    use_embedded_content  = False

    extra_css = '''
                    .news-item-title{font-size: medium ;font-family:Arial,Helvetica,sans-serif; font-weight:bold;}
                    .news-item-teaser{font-size: small ;font-family:Arial,Helvetica,sans-serif; font-weight:bold;}
                    .news-item-byline{font-size:xx-small; font-family:Arial,Helvetica,sans-serif;font-weight:normal;}
                    .news-item-text{font-size:x-small;font-family:Arial,Helvetica,sans-serif;}
                    .news-item-figure-caption-text{font-size:xx-small; font-family:Arial,Helvetica,sans-serif;font-weight:bold;}
                    .news-item-figure-caption-byline{font-size:xx-small; font-family:Arial,Helvetica,sans-serif;font-weight:normal;}
                '''

    keep_only_tags = [dict(name='div', attrs={'id':['news-item-info','news-item']})]

    remove_tags = [
                     dict(name=['object','link','embed'])
                    ,dict(name='div', attrs={'class':'related-stories'})
                  ]


    feeds = [
              (u'Infinite Loop (Apple content)'        , u'http://feeds.arstechnica.com/arstechnica/apple/'      )
             ,(u'Opposable Thumbs (Gaming content)'    , u'http://feeds.arstechnica.com/arstechnica/gaming/'     )
             ,(u'Gear and Gadgets'                     , u'http://feeds.arstechnica.com/arstechnica/gadgets/'    )
             ,(u'Chipster (Hardware content)'          , u'http://feeds.arstechnica.com/arstechnica/hardware/'   )
             ,(u'Uptime (IT content)'                  , u'http://feeds.arstechnica.com/arstechnica/business/'   )
             ,(u'Open Ended (Open Source content)'     , u'http://feeds.arstechnica.com/arstechnica/open-source/')
             ,(u'One Microsoft Way'                    , u'http://feeds.arstechnica.com/arstechnica/microsoft/'  )
             ,(u'Nobel Intent (Science content)'       , u'http://feeds.arstechnica.com/arstechnica/science/'    )
             ,(u'Law & Disorder (Tech policy content)' , u'http://feeds.arstechnica.com/arstechnica/tech-policy/')
            ]

    def append_page(self, soup, appendtag, position):
        pager = soup.find('div',attrs={'id':'pager'})
        if pager:
           for atag in pager.findAll('a',href=True):
               str = self.tag_to_string(atag)
               if str.startswith('Next'):
                  soup2 = self.index_to_soup(atag['href'])

                  texttag = soup2.find('div', attrs={'class':'news-item-text'})
                  for it in texttag.findAll(style=True):
                      del it['style']

                  newpos = len(texttag.contents)
                  self.append_page(soup2,texttag,newpos)
                  texttag.extract()
                  pager.extract()
                  appendtag.insert(position,texttag)


    def preprocess_html(self, soup):

        ftag = soup.find('div', attrs={'class':'news-item-byline'})
        if ftag:
           ftag.insert(4,'<br /><br />')

        for item in soup.findAll(style=True):
           del item['style']

        self.append_page(soup, soup.body, 3)

        return soup



