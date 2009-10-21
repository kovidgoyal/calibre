#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
www.instapaper.com
'''

from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class Instapaper(BasicNewsRecipe):
    title                 = 'Instapaper.com'
    __author__            = 'Darko Miletic'
    description           = '''Personalized news feeds. Go to instapaper.com to
                               setup up your news. Fill in your instapaper
                               username, and leave the password field
                               below blank.'''
    publisher             = 'Instapaper.com'
    category              = 'news, custom'
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    needs_subscription    = True
    INDEX                 = u'http://www.instapaper.com'
    LOGIN                 = INDEX + u'/user/login'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"'

    feeds = [
              (u'Unread articles' , INDEX + u'/u'      )
             ,(u'Starred articles', INDEX + u'/starred')
            ]

    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None:
            br.open(self.LOGIN)
            br.select_form(nr=0)
            br['username'] = self.username
            if self.password is not None:
               br['password'] = self.password
            br.submit()
        return br

    def parse_index(self):
        totalfeeds = []
        lfeeds = self.get_feeds()
        for feedobj in lfeeds:
            feedtitle, feedurl = feedobj
            self.report_progress(0, _('Fetching feed')+' %s...'%(feedtitle if feedtitle else feedurl))
            articles = []
            soup = self.index_to_soup(feedurl)
            for item in soup.findAll('div', attrs={'class':'titleRow'}):
                description = self.tag_to_string(item.div)
                atag = item.a
                if atag and atag.has_key('href'):
                    url         = self.INDEX + atag['href'] + '/text'
                    title       = self.tag_to_string(atag)
                    date        = strftime(self.timefmt)
                    articles.append({
                                      'title'      :title
                                     ,'date'       :date
                                     ,'url'        :url
                                     ,'description':description
                                    })
            totalfeeds.append((feedtitle, articles))
        return totalfeeds

