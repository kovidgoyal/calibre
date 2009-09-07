#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.adventuregamers.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class AdventureGamers(BasicNewsRecipe):
    title                 = u'Adventure Gamers'
    language = 'en'

    __author__            = 'Darko Miletic'
    description           = 'Adventure games portal'    
    publisher             = 'Adventure Gamers'
    category              = 'news, games, adventure, technology'    
    language = 'en'

    oldest_article        = 10
    delay                 = 10
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'cp1252'
    remove_javascript     = True
    use_embedded_content  = False
    INDEX                 = u'http://www.adventuregamers.com'
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    keep_only_tags = [
                       dict(name='div', attrs={'class':'content_middle'})
                     ]

    remove_tags = [
                     dict(name=['object','link','embed','form'])
                    ,dict(name='div', attrs={'class':['related-stories','article_leadout','prev','next','both']})
                  ]
                  
    remove_tags_after = [dict(name='div', attrs={'class':'toolbar_fat'})]
    
    feeds = [(u'Articles', u'http://feeds2.feedburner.com/AdventureGamers')]
    
    def get_article_url(self, article):
        return article.get('guid',  None)
    
    def append_page(self, soup, appendtag, position):
        pager = soup.find('div',attrs={'class':'toolbar_fat_next'})
        if pager:
           nexturl = self.INDEX + pager.a['href']
           soup2 = self.index_to_soup(nexturl)
           texttag = soup2.find('div', attrs={'class':'bodytext'})
           for it in texttag.findAll(style=True):
               del it['style']
           newpos = len(texttag.contents)          
           self.append_page(soup2,texttag,newpos)
           texttag.extract()
           appendtag.insert(position,texttag)
        
    
    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="en-US"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        self.append_page(soup, soup.body, 3)
        pager = soup.find('div',attrs={'class':'toolbar_fat'})
        if pager:
           pager.extract()        
        return soup
