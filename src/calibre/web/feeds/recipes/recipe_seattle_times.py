#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
seattletimes.nwsource.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class SeattleTimes(BasicNewsRecipe):
    title                 = 'The Seattle Times'
    __author__            = 'Darko Miletic'
    description           = 'News from Seattle and USA'
    publisher             = 'The Seattle Times'
    category              = 'news, politics, USA'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    language = 'en'


    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        ]

    html2epub_options  = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    feeds              = [(u'Articles', u'http://seattletimes.nwsource.com/rss/seattletimes.xml')]

    remove_tags        = [
                             dict(name=['object','link','script'])
                            ,dict(name='p', attrs={'class':'permission'})
                         ]

    def print_version(self, url):
        start_url, sep, rest_url = url.rpartition('_')
        rurl, rsep, article_id = start_url.rpartition('/')
        return u'http://seattletimes.nwsource.com/cgi-bin/PrintStory.pl?document_id=' + article_id

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="en-US"/>'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']
        return soup

