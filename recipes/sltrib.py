from calibre.web.feeds.news import BasicNewsRecipe

class AdvancedUserRecipe1278347258(BasicNewsRecipe):
    title      = u'Salt Lake City Tribune'
    __author__ = 'Charles Holbert'
    oldest_article = 7
    max_articles_per_feed = 100

    description            = '''Utah's independent news source since 1871'''
    publisher              = 'http://www.sltrib.com/'
    category               = 'news, Utah, SLC'
    language               = 'en'
    encoding               = 'utf-8'
    #delay                  = 1
    #simultaneous_downloads = 1
    remove_javascript      = True
    use_embedded_content   = False
    no_stylesheets         = True

    #masthead_url = 'http://www.sltrib.com/csp/cms/sites/sltrib/assets/images/logo_main.png'
    #cover_url = 'http://webmedia.newseum.org/newseum-multimedia/dfp/jpg9/lg/UT_SLT.jpg'

    keep_only_tags = [dict(name='div',attrs={'id':'imageBox'})
                      ,dict(name='div',attrs={'class':'headline'})
                      ,dict(name='div',attrs={'class':'byline'})
                      ,dict(name='p',attrs={'class':'TEXT_w_Indent'})]

    feeds = [(u'SL Tribune Today', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rss.csp?cat=All'),
           (u'Utah News', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rss.csp?cat=UtahNews'),
           (u'Business News', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rss.csp?cat=Money'),
           (u'Technology', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rss.csp?cat=Technology'),
           (u'Most Popular', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rsspopular.csp'),
           (u'Sports', u'http://www.sltrib.com/csp/cms/sites/sltrib/RSS/rss.csp?cat=Sports')]

    extra_css = '''
                .headline{font-family:Arial,Helvetica,sans-serif; font-size:xx-large; font-weight: bold; color:#0E5398;}
                .byline{font-family:Arial,Helvetica,sans-serif; color:#333333; font-size:xx-small;}
                .storytext{font-family:Arial,Helvetica,sans-serif; font-size:medium;}
                '''

    def print_version(self, url):
        seg = url.split('/')
        x = seg[5].split('-')
        baseURL = 'http://www.sltrib.com/csp/cms/sites/sltrib/pages/printerfriendly.csp?id='
        s = baseURL + x[0]
        return s

    def get_cover_url(self):
        cover_url = None
        href =  'http://www.newseum.org/todaysfrontpages/hr.asp?fpVname=UT_SLT&ref_pge=lst'
        soup = self.index_to_soup(href)
        div = soup.find('div',attrs={'class':'tfpLrgView_container'})
        if div:
            cover_url = div.img['src']
        return cover_url

