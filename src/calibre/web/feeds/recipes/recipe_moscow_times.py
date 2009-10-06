#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
moscowtimes.ru
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Moscowtimes(BasicNewsRecipe):
    title                 = u'The Moscow Times'
    __author__            = 'Darko Miletic and Sujata Raman'
    description           = 'News from Russia'
    language = 'en'
    lang = 'en'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    #encoding = 'utf-8'
    encoding =  'cp1252'
    remove_javascript = True

    conversion_options = {
          'comment'          : description
        , 'language'         : lang
    }

    extra_css      = '''
                        h1{ color:#0066B3; font-family: Georgia,serif ; font-size: large}
                        .article_date{ font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; color:#000000; font-size: x-small;}
                        .autors{color:#999999 ; font-weight: bold ; font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; font-size: x-small; }
                        .photoautors{ color:#999999 ; font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; font-size: x-small; }
                        .text{font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; font-size:75%; }
                        '''
    feeds          = [
                        (u'The Moscow Times Top Stories' , u'http://www.themoscowtimes.com/rss/top'),
                        (u'The Moscow Times Current Issue' , u'http://www.themoscowtimes.com/rss/issue'),
                        (u'The Moscow Times News' , u'http://www.themoscowtimes.com/rss/news'),
                        (u'The Moscow Times Business' , u'http://www.themoscowtimes.com/rss/business'),
                        (u'The Moscow Times Art and Ideas' , u'http://www.themoscowtimes.com/rss/art'),
                        (u'The Moscow Times Opinion' , u'http://www.themoscowtimes.com/rss/opinion')
                     ]

    keep_only_tags = [
                        dict(name='div', attrs={'class':['newstextblock']})
                    ]

    remove_tags    = [
                        dict(name='div', attrs={'class':['photo_nav']})
                    ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
        soup.head.insert(0,mtag)

        return self.adeify_images(soup)


    def get_cover_url(self):

        href =  'http://www.themoscowtimes.com/pdf/'

        soup = self.index_to_soup(href)
        div = soup.find('div',attrs={'class':'left'})
        a = div.find('a')
        print a
        if a :
           cover_url = a.img['src']
        return cover_url
