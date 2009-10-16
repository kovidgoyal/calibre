#!/usr/bin/env  python
# -*- coding: cp1252 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
honoluluadvertiser.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Honoluluadvertiser(BasicNewsRecipe):
    title                 = 'Honolulu Advertiser'
    __author__            = 'Darko Miletic and Sujata Raman'
    description           = "Latest national and local Hawaii sports news from The Honolulu Advertiser."
    publisher             = 'Honolulu Advertiser'
    category              = 'news, Honolulu, Hawaii'
    oldest_article        = 2
    language = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    remove_javascript     = True
    cover_url             = 'http://www.honoluluadvertiser.com/graphics/frontpage/frontpage.jpg'

    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , category
                        , '--publisher'     , publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    keep_only_tags = [dict(name='div', attrs={'class':["hon_article_top","article-bodytext","hon_article_photo","storyphoto","article"]}),
                      dict(name='div', attrs={'id':["storycontentleft","article"]})
                      ]

    remove_tags = [dict(name=['object','link','embed']),
                   dict(name='div', attrs={'class':["article-tools","titleBar","invisiblespacer","articleflex-container","hon_newslist","categoryheader","columnframe","subHeadline","poster-container"]}),
                   dict(name='div', attrs={'align':["right"]}),
                   dict(name='div', attrs={'id':["pluckcomments"]}),
                   dict(name='td', attrs={'class':["prepsfacts"]}),
                   dict(name='img', attrs={'height':["1"]}),
                   dict(name='img', attrs={'alt':["Advertisement"]}),
                   dict(name='img', attrs={'src':["/gcicommonfiles/sr/graphics/common/adlabel_horz.gif","/gcicommonfiles/sr/graphics/common/icon_whatsthis.gif",]}),
                   ]

    extra_css = '''
                    h1{font-family:Arial,Helvetica,sans-serif; font-size:large; color:#000000; }
                    .hon_article_timestamp{font-family:Arial,Helvetica,sans-serif; font-size:70%; }
                    .postedStoryDate{font-family:Arial,Helvetica,sans-serif; font-size:30%; }
                    .postedDate{font-family:Arial,Helvetica,sans-serif; font-size:30%; }
                    .credit{font-family:Arial,Helvetica,sans-serif; font-size:30%; }
                    .hon_article_top{font-family:Arial,Helvetica,sans-serif; color:#666666; font-size:30%; font-weight:bold;}
                    .grayBackground{font-family:Arial,Helvetica,sans-serif; color:#666666; font-size:30%;}
                    .hon_photocaption{font-family:Arial,Helvetica,sans-serif; font-size:30%; }
                    .photoCaption{font-family:Arial,Helvetica,sans-serif; font-size:30%; }
                    .hon_photocredit{font-family:Arial,Helvetica,sans-serif; font-size:30%; color:#666666;}
                    .storyphoto{font-family:Arial,Helvetica,sans-serif; font-size:30%; color:#666666;}
                    .article-bodytext{font-family:Arial,Helvetica,sans-serif; font-size:xx-small; }
                    .storycontentleft{font-family:Arial,Helvetica,sans-serif; font-size:xx-small; }
                    #article{font-family:Arial,Helvetica,sans-serif; font-size:xx-small; }
                    .contentarea{font-family:Arial,Helvetica,sans-serif; font-size:xx-small; }
                    .storytext{font-family:Verdana,Arial,Helvetica,sans-serif; font-size:xx-small;}
                    .storyHeadline{font-family:Arial,Helvetica,sans-serif; font-size:large; color:#000000; font-weight:bold;}
                    .source{font-family:Arial,Helvetica,sans-serif; color:#333333; font-style: italic; font-weight:bold; }
                '''

    feeds = [
              (u'Breaking news', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS01&MIME=XML' )
             ,(u'Local news', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS02&MIME=XML' )
             ,(u'Sports', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS03&MIME=XML' )
             ,(u'Island life', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS05&MIME=XML' )
             ,(u'Entertainment', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS06&MIME=XML' )
             ,(u'Business', u'http://www.honoluluadvertiser.com/apps/pbcs.dll/section?Category=RSS04&MIME=XML' )
            ]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        mtag = '\n<meta http-equiv="Content-Language" content="en"/>\n'
        soup.head.insert(0,mtag)

        for tag in soup.findAll(name=['span','table','font']):
               tag.name = 'div'

        return soup


   # def print_version(self, url):
   #     ubody, sep, rest = url.rpartition('/-1/')
   #     root, sep2, article_id = ubody.partition('/article/')
   #     return u'http://www.honoluluadvertiser.com/apps/pbcs.dll/article?AID=/' + article_id + '&template=printart'

