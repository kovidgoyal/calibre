#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
lrb.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LondonReviewOfBooks(BasicNewsRecipe):
    title                 = u'London Review of Books'
    __author__            = u'Darko Miletic'
    description           = u'Literary review publishing essay-length book reviews and topical articles on politics, literature, history, philosophy, science and the arts by leading writers and thinkers'
    oldest_article        = 7
    max_articles_per_feed = 100
    language = 'en'

    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    
    remove_tags = [
                    dict(name='div' , attrs={'id'   :'otherarticles'})
                   ,dict(name='div' , attrs={'class':'pagetools'    })
                   ,dict(name='div' , attrs={'id'   :'mainmenu'     })
                   ,dict(name='div' , attrs={'id'   :'precontent'   })
                   ,dict(name='div' , attrs={'class':'nocss'        })
                   ,dict(name='span', attrs={'class':'inlineright'  })
                  ]
    
    feeds = [(u'London Review of Books', u'http://www.lrb.co.uk/lrbrss.xml')]

    def print_version(self, url):
        main, split, rest = url.rpartition('/')
        return main + '/print/' + rest
    
    def postprocess_html(self, soup, first_fetch):
        for t in soup.findAll(['table', 'tr', 'td']):
            t.name = 'div'
        return soup
