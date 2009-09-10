#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
sciencedaily.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class ScienceDaily(BasicNewsRecipe):
    title                 = u'ScienceDaily'
    __author__            = u'Darko Miletic'
    description           = u"Breaking science news and articles on global warming, extrasolar planets, stem cells, bird flu, autism, nanotechnology, dinosaurs, evolution -- the latest discoveries in astronomy, anthropology, biology, chemistry, climate &amp; environment, computers, engineering, health &amp; medicine, math, physics, psychology, technology, and more -- from the world's leading universities and research organizations."
    oldest_article        = 7
    language = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    
    cover_url = 'http://www.sciencedaily.com/images/logo.gif'
    
    keep_only_tags = [ 
                        dict(name='h1', attrs={'class':'story'}) 
                       ,dict(name='div', attrs={'id':'story'}) 
                     ]
                     
    remove_tags_after = dict(name='div', attrs={'id':'citationbox'})
    remove_tags = [
                     dict(name='div', attrs={'id':'seealso'})
                    ,dict(name='div', attrs={'id':'citationbox'})
                  ]
    
    feeds       = [(u"ScienceDaily", u'http://www.sciencedaily.com/newsfeed.xml')]
