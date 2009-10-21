from calibre.web.feeds.news import BasicNewsRecipe

class SecurityWatch(BasicNewsRecipe):
    title          = u'securitywatch'
    description = 'security news'
    timefmt  = ' [%d %b %Y]'
    __author__ = 'Oliver Niesner'
    no_stylesheets = True
    oldest_article = 14
    max_articles_per_feed = 100
    use_embedded_content = False
    filter_regexps = [r'feedads\.googleadservices\.com']
    filter_regexps = [r'ad\.doubleclick']
    filter_regexps = [r'advert']
    language = 'en'

    extra_css = 'div {text-align:left}'
    
    remove_tags = [dict(id='topBannerContainer'),
                   dict(id='topBannerSmall'),
                   dict(id='topSearchBar'),
                   dict(id='topSearchForm'),
                   dict(id='rtBannerMPU'),
                   dict(id='topNavBar'),
                   dict(id='breadcrumbs'),
                   #dict(id='entry-28272'),
                   dict(id='topSearchLinks'),
                   dict(name='span', attrs={'class':'date'})]
    
    remove_tags_after = [dict(id='googlemp')]
    
    feeds          = [(u'securitywatch', u'http://feeds.ziffdavisenterprise.com/RSS/security_watch/')]


    def postprocess_html(self, soup, first_fetch):
        for t in soup.findAll(['table', 'tr', 'td']):
            t.name = 'div'
        return soup
