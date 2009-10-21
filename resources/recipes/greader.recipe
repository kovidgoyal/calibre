import urllib, re, mechanize
from calibre.web.feeds.recipes import BasicNewsRecipe
from calibre import __appname__

class GoogleReader(BasicNewsRecipe):
    title   = 'Google Reader'
    description = 'This recipe downloads feeds you have tagged from your Google Reader account.'
    needs_subscription = True
    __author__ = 'davec'
    base_url = 'http://www.google.com/reader/atom/'
    max_articles_per_feed = 50
    get_options = '?n=%d&xt=user/-/state/com.google/read' % max_articles_per_feed
    use_embedded_content = True

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()

        if self.username is not None and self.password is not None:
            request = urllib.urlencode([('Email', self.username), ('Passwd', self.password),
                                        ('service', 'reader'), ('source', __appname__)])
            response = br.open('https://www.google.com/accounts/ClientLogin', request)
            sid = re.search('SID=(\S*)', response.read()).group(1)

            cookies = mechanize.CookieJar()
            br = mechanize.build_opener(mechanize.HTTPCookieProcessor(cookies))
            cookies.set_cookie(mechanize.Cookie(None, 'SID', sid, None, False, '.google.com', True, True, '/', True, False, None, True, '', '', None))
        return br


    def get_feeds(self):
        feeds = []
        soup = self.index_to_soup('http://www.google.com/reader/api/0/tag/list')
        for id in soup.findAll(True, attrs={'name':['id']}):
            url = id.contents[0]
            feeds.append((re.search('/([^/]*)$', url).group(1), 
                          self.base_url + urllib.quote(url.encode('utf-8')) + self.get_options))
        return feeds
