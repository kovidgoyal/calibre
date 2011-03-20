#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.livemint.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LiveMint(BasicNewsRecipe):
    title                 = u'Livemint'
    __author__            = 'Darko Miletic'
    description           = 'The Wall Street Journal'
    publisher             = 'The Wall Street Journal'
    category              = 'news, games, adventure, technology'
    language = 'en'

    oldest_article        = 15
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    extra_css             = ' #dvArtheadline{font-size: x-large} #dvArtAbstract{font-size: large} '

    keep_only_tags = [dict(name='div', attrs={'class':'innercontent'})]

    remove_tags = [dict(name=['object','link','embed','form','iframe'])]

    feeds = [(u'Articles', u'http://www.livemint.com/SectionRssfeed.aspx?Mid=1')]

    def print_version(self, url):
        link = url
        msoup = self.index_to_soup(link)
        mlink = msoup.find(attrs={'id':'ctl00_bodyplaceholdercontent_cntlArtTool_printUrl'})
        if mlink:
           link = 'http://www.livemint.com/Articles/' + mlink['href'].rpartition('/Articles/')[2]
        return link

    def preprocess_html(self, soup):
        return self.adeify_images(soup)
