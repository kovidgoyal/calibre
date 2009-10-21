#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.corriere.it/english
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Corriere_en(BasicNewsRecipe):
    title                 = 'Corriere della Sera in English'
    __author__            = 'Darko Miletic'
    description           = 'News from Milan and Italy'
    oldest_article        = 15
    publisher             = 'Corriere della Sera'
    category              = 'news, politics, Italy'
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    remove_javascript     = True
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True'

    keep_only_tags = [dict(name='div', attrs={'class':['news-dettaglio article','article']})]

    remove_tags = [
                    dict(name=['base','object','link','embed','img'])
                   ,dict(name='div', attrs={'class':'news-goback'})
                   ,dict(name='ul', attrs={'class':'toolbar'})
                  ]

    remove_tags_after = dict(name='p', attrs={'class':'footnotes'})

    feeds = [(u'Italian Life', u'http://www.corriere.it/rss/english.xml')]

