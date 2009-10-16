#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.inquirer.net
'''

from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import Tag

class InquirerNet(BasicNewsRecipe):
    title                  = 'Inquirer.net'
    __author__             = 'Darko Miletic'
    description            = 'News from Philipines'
    oldest_article         = 2
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    encoding               = 'cp1252'
    publisher              = 'inquirer.net'
    category               = 'news, politics, philipines'
    lang                   = 'en'
    language = 'en'

    extra_css              = ' .fontheadline{font-size: x-large} .fontsubheadline{font-size: large} .fontkick{font-size: medium}'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    remove_tags = [dict(name=['object','link','script','iframe','form'])]

    feeds = [
               (u'Breaking news', u'http://services.inquirer.net/rss/breakingnews.xml'             )
              ,(u'Top stories'  , u'http://services.inquirer.net/rss/topstories.xml'               )
              ,(u'Sports'       , u'http://services.inquirer.net/rss/brk_breakingnews.xml'         )
              ,(u'InfoTech'     , u'http://services.inquirer.net/rss/infotech_tech.xml'            )
              ,(u'InfoTech'     , u'http://services.inquirer.net/rss/infotech_tech.xml'            )
              ,(u'Business'     , u'http://services.inquirer.net/rss/inq7money_breaking_news.xml'  )
              ,(u'Editorial'    , u'http://services.inquirer.net/rss/opinion_editorial.xml'        )
              ,(u'Global Nation', u'http://services.inquirer.net/rss/globalnation_breakingnews.xml')
            ]

    def preprocess_html(self, soup):
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=utf-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    def print_version(self, url):
        rest, sep, art = url.rpartition('/view/')
        art_id, sp, rrest = art.partition('/')
        return 'http://services.inquirer.net/print/print.php?article_id=' + art_id
