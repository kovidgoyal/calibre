#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.smashingmagazine.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class SmashingMagazine(BasicNewsRecipe):
    title                 = 'Smashing Magazine'
    __author__            = 'Darko Miletic'
    description           = 'We smash you with the information that will make your life easier, really'
    oldest_article        = 20
    language              = 'en'
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    publisher             = 'Smashing Magazine'
    category              = 'news, web, IT, css, javascript, html'
    encoding              = 'utf-8'

    conversion_options = {
                             'comments'    : description
                            ,'tags'        : category
                            ,'publisher'   : publisher
                         }

    keep_only_tags = [dict(name='div', attrs={'id':'leftcolumn'})]
    remove_tags_after = dict(name='ul',attrs={'class':'social'})
    remove_tags = [
                    dict(name=['link','object'])
                   ,dict(name='h1',attrs={'class':'logo'})
                   ,dict(name='div',attrs={'id':'booklogosec'})
                   ,dict(attrs={'src':'http://media2.smashingmagazine.com/wp-content/uploads/images/the-smashing-book/smbook6.gif'})
                  ]

    feeds          = [(u'Articles', u'http://rss1.smashingmagazine.com/feed/')]

    def preprocess_html(self, soup):
        for iter in soup.findAll('div',attrs={'class':'leftframe'}):
            it = iter.find('h1')
            if it == None:
               iter.extract()
        for item in soup.findAll('img'):
            oldParent = item.parent
            if oldParent.name == 'a':
               oldParent.name = 'div'
        return soup
