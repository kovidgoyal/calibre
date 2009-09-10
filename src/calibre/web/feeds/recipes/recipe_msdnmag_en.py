#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
msdn.microsoft.com/en-us/magazine
'''
from calibre.web.feeds.news import BasicNewsRecipe

class MSDNMagazine_en(BasicNewsRecipe):
    title                 = 'MSDN Magazine'
    __author__            = 'Darko Miletic'
    description           = 'The Microsoft Journal for Developers'
    publisher             = 'Microsoft Press'
    category              = 'news, IT, Microsoft, programming, windows'
    oldest_article        = 31
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    remove_javascript     = True
    current_issue         = 'http://msdn.microsoft.com/en-us/magazine/default.aspx'
    language = 'en'


    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    feeds = [(u'Articles', u'http://msdn.microsoft.com/en-us/magazine/rss/default.aspx?z=z&iss=1')]

    keep_only_tags = [dict(name='div', attrs={'class':'topic'})]

    remove_tags = [
                     dict(name=['object','link','base','table'])
                    ,dict(name='div', attrs={'class':'MTPS_CollapsibleRegion'})
                  ]

    def get_cover_url(self):
        cover_url = None
        soup = self.index_to_soup(self.current_issue)
        link_item = soup.find('span',attrs={'class':'ContentsImageSpacer'})
        if link_item:
           imgt = link_item.find('img')
           if imgt:
              cover_url = imgt['src']
        return cover_url


    def preprocess_html(self, soup):
        for item in soup.findAll('div',attrs={'class':['FeatureSmallHead','ColumnTypeSubTitle']}):
            item.name="h2"
        for item in soup.findAll('div',attrs={'class':['FeatureHeadline','ColumnTypeTitle']}):
            item.name="h1"
        for item in soup.findAll('div',attrs={'class':'ArticleTypeTitle'}):
            item.name="h3"
        return soup

