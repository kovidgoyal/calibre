#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
sciencenews.org
'''
from calibre.web.feeds.news import BasicNewsRecipe

class Sciencenews(BasicNewsRecipe):
    title                 = u'ScienceNews'
    __author__            = u'Darko Miletic'
    description           = u"Science News is an award-winning weekly newsmagazine covering the most important research in all fields of science. Its 16 pages each week are packed with short, accurate articles that appeal to both general readers and scientists. Published since 1922, the magazine now reaches about 150,000 subscribers and more than 1 million readers. These are the latest News Items from Science News."
    oldest_article        = 30
    language = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 

    keep_only_tags = [ dict(name='div', attrs={'id':'column_action'}) ]
    remove_tags_after = dict(name='ul', attrs={'id':'content_functions_bottom'})
    remove_tags = [
                     dict(name='ul', attrs={'id':'content_functions_bottom'})
                    ,dict(name='div', attrs={'id':'content_functions_top'})
                  ]

    feeds       = [(u"Science News / News Items", u'http://sciencenews.org/view/feed/type/news/name/news.rss')]
