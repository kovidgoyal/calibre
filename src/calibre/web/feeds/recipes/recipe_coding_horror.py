#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.codinghorror.com/blog/
'''

from calibre.web.feeds.news import BasicNewsRecipe

class CodingHorror(BasicNewsRecipe):
    title                 = 'Coding Horror'
    __author__            = 'Darko Miletic'
    description           = 'programming and human factors - Jeff Atwood'
    category              = 'blog, programming'
    publisher             = 'Jeff Atwood'
    language = 'en'

    author                = 'Jeff Atwood'
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = True
    encoding              = 'cp1252'

    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--author'   , author
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nauthors="' + author + '"'

    remove_tags = [
                     dict(name=['object','link'])
                    ,dict(name='div',attrs={'class':'feedflare'})
                  ]

    feeds = [(u'Articles', u'http://feeds2.feedburner.com/codinghorror' )]

