#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
sptimes.ru
'''

from calibre.web.feeds.news import BasicNewsRecipe

class PetersburgTimes(BasicNewsRecipe):
    title                 = 'The St. Petersburg Times'
    __author__            = 'Darko Miletic'
    description           = 'News from Russia'
    publisher             = 'sptimes.ru'
    category              = 'news, politics, Russia'
    max_articles_per_feed = 100
    no_stylesheets        = True
    remove_javascript     = True
    encoding              = 'cp1251'
    use_embedded_content  = False
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    remove_tags = [dict(name=['object','link','embed'])]

    feeds = [(u'Headlines', u'http://sptimes.ru/headlines.php' )]

    def preprocess_html(self, soup):
        return self.adeify_images(soup)

    def get_article_url(self, article):
        raw = article.get('guid',  None)
        return raw

    def print_version(self, url):
        start_url, question, article_id = url.rpartition('/')
        return u'http://www.sptimes.ru/index.php?action_id=100&story_id=' + article_id

