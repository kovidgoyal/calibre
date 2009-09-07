#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

# http://online.wsj.com/page/us_in_todays_paper.html

class WallStreetJournal(BasicNewsRecipe):

        title = 'The Wall Street Journal'
        __author__ = 'Kovid Goyal and Sujata Raman'
        description = 'News and current affairs.'
        needs_subscription = True
        language = 'en'

        max_articles_per_feed = 10
        timefmt  = ' [%a, %b %d, %Y]'
        no_stylesheets = True

        extra_css      = '''h1{color:#093D72 ; font-size:large ; font-family:Georgia,"Century Schoolbook","Times New Roman",Times,serif; }
                        h2{color:#474537; font-family:Georgia,"Century Schoolbook","Times New Roman",Times,serif; font-size:small; font-style:italic;}
                        .subhead{color:gray; font-family:Georgia,"Century Schoolbook","Times New Roman",Times,serif; font-size:small; font-style:italic;}
                        .insettipUnit {color:#666666; font-family:Arial,Sans-serif;font-size:xx-small }
                        .targetCaption{ font-size:x-small; color:#333333; font-family:Arial,Helvetica,sans-serif}
                        .article{font-family :Arial,Helvetica,sans-serif; font-size:x-small}
                        .tagline {color:#333333; font-size:xx-small}
                        .dateStamp {color:#666666; font-family:Arial,Helvetica,sans-serif}
                         h3{color:blue ;font-family:Arial,Helvetica,sans-serif; font-size:xx-small}
                         .byline{color:blue;font-family:Arial,Helvetica,sans-serif; font-size:xx-small}
                         h6{color:#333333; font-family:Georgia,"Century Schoolbook","Times New Roman",Times,serif; font-size:small;font-style:italic; }
                        .paperLocation{color:#666666; font-size:xx-small}'''

        remove_tags_before = dict(name='h1')
        remove_tags = [
                       dict(id=["articleTabs_tab_article", "articleTabs_tab_comments", "articleTabs_tab_interactive","articleTabs_tab_video","articleTabs_tab_map","articleTabs_tab_slideshow"]),
                       {'class':['footer_columns','network','insetCol3wide','interactive','video','slideshow','map','insettip','insetClose','more_in', "insetContent", 'articleTools_bottom', 'aTools', "tooltip", "adSummary", "nav-inline"]},
                       dict(rel='shortcut icon'),
                      ]
        remove_tags_after = [dict(id="article_story_body"), {'class':"article story"},]


        def get_browser(self):
            br = BasicNewsRecipe.get_browser()
            if self.username is not None and self.password is not None:
                br.open('http://commerce.wsj.com/auth/login')
                br.select_form(nr=0)
                br['user']   = self.username
                br['password'] = self.password
                br.submit()
            return br

        def postprocess_html(self, soup, first):
            for tag in soup.findAll(name=['table', 'tr', 'td']):
                tag.name = 'div'

            for tag in soup.findAll('div', dict(id=["articleThumbnail_1", "articleThumbnail_2", "articleThumbnail_3", "articleThumbnail_4", "articleThumbnail_5", "articleThumbnail_6", "articleThumbnail_7"])):
                tag.extract()

            return soup

        def get_article_url(self, article):
            try:
                return article.feedburner_origlink.split('?')[0]
            except AttributeError:
                return article.link.split('?')[0]

        def cleanup(self):
            self.browser.open('http://online.wsj.com/logout?url=http://online.wsj.com')

        feeds =  [
                #('Most Emailed - Day', 'http://online.wsj.com/xml/rss/3_7030.xml'),
                #('Most Emailed - Week', 'http://online.wsj.com/xml/rss/3_7253.xml'),
                #('Most Emailed - Month', 'http://online.wsj.com/xml/rss/3_7254.xml'),
                (' Most Viewed - Day', 'http://online.wsj.com/xml/rss/3_7198.xml'),
                (' Most Viewed - Week', 'http://online.wsj.com/xml/rss/3_7251.xml'),
                #('Most Viewed - Month', 'http://online.wsj.com/xml/rss/3_7252.xml'),
                ('Today\'s Newspaper -  Page One', 'http://online.wsj.com/xml/rss/3_7205.xml'),
                ('Today\'s Newspaper - Marketplace', 'http://online.wsj.com/xml/rss/3_7206.xml'),
                ('Today\'s Newspaper - Money & Investing', 'http://online.wsj.com/xml/rss/3_7207.xml'),
                ('Today\'s Newspaper - Personal Journal', 'http://online.wsj.com/xml/rss/3_7208.xml'),
                ('Today\'s Newspaper - Weekend Journal', 'http://online.wsj.com/xml/rss/3_7209.xml'),
                ('Opinion', 'http://online.wsj.com/xml/rss/3_7041.xml'),
                ('News - U.S.: What\'s News', 'http://online.wsj.com/xml/rss/3_7011.xml'),
                ('News - U.S. Business', 'http://online.wsj.com/xml/rss/3_7014.xml'),
                ('News - Europe: What\'s News', 'http://online.wsj.com/xml/rss/3_7012.xml'),
                ('News - Asia: What\'s News', 'http://online.wsj.com/xml/rss/3_7013.xml'),
                ('News - World News', 'http://online.wsj.com/xml/rss/3_7085.xml'),
                ('News - Economy', 'http://online.wsj.com/xml/rss/3_7086.xml'),
                ('News - Earnings', 'http://online.wsj.com/xml/rss/3_7088.xml'),
                ('News - Health', 'http://online.wsj.com/xml/rss/3_7089.xml'),
                ('News - Law', 'http://online.wsj.com/xml/rss/3_7091.xml'),
                ('News - Media & Marketing', 'http://online.wsj.com/xml/rss/3_7020.xml'),
                ('Technology - What\'s News', 'http://online.wsj.com/xml/rss/3_7015.xml'),
                ('Technology - Gadgets', 'http://online.wsj.com/xml/rss/3_7094.xml'),
                ('Technology - Telecommunications', 'http://online.wsj.com/xml/rss/3_7095.xml'),
                ('Technology - E-commerce/Media', 'http://online.wsj.com/xml/rss/3_7096.xml'),
                ('Technology - Asia', 'http://online.wsj.com/xml/rss/3_7097.xml'),
                ('Technology - Europe', 'http://online.wsj.com/xml/rss/3_7098.xml'),
                ('Markets - News', 'http://online.wsj.com/xml/rss/3_7031.xml'),
                ('Markets - Europe News', 'http://online.wsj.com/xml/rss/3_7101.xml'),
                ('Markets - Asia News', 'http://online.wsj.com/xml/rss/3_7102.xml'),
                ('Markets - Deals & Deal Makers', 'http://online.wsj.com/xml/rss/3_7099.xml'),
                ('Markets - Hedge Funds', 'http://online.wsj.com/xml/rss/3_7199.xml'),
                ('Personal Journal', 'http://online.wsj.com/xml/rss/3_7200.xml'),
                ('Personal Journal - Money', 'http://online.wsj.com/xml/rss/3_7104.xml'),
                ('Personal Journal - Health', 'http://online.wsj.com/xml/rss/3_7089.xml'),
                ('Personal Journal - Autos', 'http://online.wsj.com/xml/rss/3_7092.xml'),
                ('Personal Journal - Homes', 'http://online.wsj.com/xml/rss/3_7105.xml'),
                ('Personal Journal - Travel', 'http://online.wsj.com/xml/rss/3_7106.xml'),
                ('Personal Journal - Careers', 'http://online.wsj.com/xml/rss/3_7107.xml'),
                ('Weekend & Leisure', 'http://online.wsj.com/xml/rss/3_7201.xml'),
                ('Weekend & Leisure - Weekend Journal', 'http://online.wsj.com/xml/rss/3_7202.xml'),
                ('Weekend & Leisure - Arts & Entertainment', 'http://online.wsj.com/xml/rss/3_7177.xml'),
                ('Weekend & Leisure - Books', 'http://online.wsj.com/xml/rss/3_7203.xml'),
                ('Weekend & Leisure - Sports', 'http://online.wsj.com/xml/rss/3_7204.xml'),
                ]

