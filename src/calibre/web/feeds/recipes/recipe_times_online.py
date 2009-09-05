#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
timesonline.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Timesonline(BasicNewsRecipe):
    title                  = 'The Times Online'
    __author__             = 'Darko Miletic'
    description            = 'UK news' 
    publisher              = 'timesonline.co.uk'
    category               = 'news, politics, UK'        
    oldest_article         = 2
    max_articles_per_feed  = 100
    no_stylesheets         = True
    use_embedded_content   = False
    simultaneous_downloads = 1
    encoding               = 'cp1252'
    lang                   = 'en-UK'
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
    
    remove_tags        = [dict(name=['embed','object'])]
    remove_tags_after  = dict(name='div', attrs={'class':'bg-666'})

    feeds          = [
                        (u'Top stories from Times Online', u'http://www.timesonline.co.uk/tol/feeds/rss/topstories.xml'     ),
                        ('Latest Business News', 'http://www.timesonline.co.uk/tol/feeds/rss/business.xml'),
                        ('Economics', 'http://www.timesonline.co.uk/tol/feeds/rss/economics.xml'),
                        ('World News', 'http://www.timesonline.co.uk/tol/feeds/rss/worldnews.xml'),
                        ('UK News', 'http://www.timesonline.co.uk/tol/feeds/rss/uknews.xml'),
                        ('Travel News', 'http://www.timesonline.co.uk/tol/feeds/rss/travel.xml'),
                        ('Sports News', 'http://www.timesonline.co.uk/tol/feeds/rss/sport.xml'),
                        ('Film News', 'http://www.timesonline.co.uk/tol/feeds/rss/film.xml'),
                        ('Tech news', 'http://www.timesonline.co.uk/tol/feeds/rss/tech.xml'),
                        ('Literary Supplement', 'http://www.timesonline.co.uk/tol/feeds/rss/thetls.xml'),
                     ]

    def print_version(self, url):
        return url + '?print=yes'

    def get_article_url(self, article):
        return article.get('guid',  None)

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mlang = Tag(soup,'meta',[("http-equiv","Content-Language"),("content",self.lang)])
        mcharset = Tag(soup,'meta',[("http-equiv","Content-Type"),("content","text/html; charset=UTF-8")])
        soup.head.insert(0,mlang)
        soup.head.insert(1,mcharset)
        return self.adeify_images(soup)
        