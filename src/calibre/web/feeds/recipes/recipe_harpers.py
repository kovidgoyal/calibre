#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
harpers.org
'''
from calibre.web.feeds.news import BasicNewsRecipe

class Harpers(BasicNewsRecipe):
    title                 = u"Harper's Magazine"
    __author__            = u'Darko Miletic'
    language              = _('English')
    description           = u"Harper's Magazine: Founded June 1850."
    publisher             = "Harper's Magazine "
    category              = 'news, politics, USA'
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"' 
    
    
    keep_only_tags = [ dict(name='div', attrs={'id':'cached'}) ]
    remove_tags = [
                     dict(name='table', attrs={'class':'rcnt'})
                    ,dict(name='table', attrs={'class':'rcnt topline'})
                    ,dict(name=['link','object','embed'])
                  ]

    feeds       = [(u"Harper's Magazine", u'http://www.harpers.org/rss/frontpage-rss20.xml')]

