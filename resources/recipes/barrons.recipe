##
##    web2lrf profile to download articles from Barrons.com
##    can download subscriber-only content if username and
##    password are supplied.
##
'''
'''

import re

from calibre.web.feeds.news import BasicNewsRecipe

class Barrons(BasicNewsRecipe):

        title = 'Barron\'s'
        max_articles_per_feed = 50
        needs_subscription    = True
        language = 'en'

        __author__ = 'Kovid Goyal'
        description = 'Weekly publication for investors from the publisher of the Wall Street Journal'
        timefmt  = ' [%a, %b %d, %Y]'
        use_embedded_content   = False
        no_stylesheets = False
        match_regexps = ['http://online.barrons.com/.*?html\?mod=.*?|file:.*']
        conversion_options = {'linearize_tables': True}
        ##delay = 1

        ## Don't grab articles more than 7 days old
        oldest_article = 7


        preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
                [
                ## Remove anything before the body of the article.
                (r'<body.*?<!-- article start', lambda match: '<body><!-- article start'),

                ## Remove any insets from the body of the article.
                (r'<div id="inset".*?</div>.?</div>.?<p', lambda match : '<p'),

                ## Remove any reprint info from the body of the article.
                (r'<hr size.*?<p', lambda match : '<p'),

                ## Remove anything after the end of the article.
                (r'<!-- article end.*?</body>', lambda match : '</body>'),
                ]
        ]

        def get_browser(self):
            br = BasicNewsRecipe.get_browser()
            if self.username is not None and self.password is not None:
                br.open('http://commerce.barrons.com/auth/login')
                br.select_form(name='login_form')
                br['user']   = self.username
                br['password'] = self.password
                br.submit()
            return br

## Use the print version of a page when available.

        def print_version(self, url):
                return url.replace('/article/', '/article_print/')

## Comment out the feeds you don't want retrieved.
## Because these feeds are sorted alphabetically when converted to LRF, you may want to number them to put them in the order you desire

        def get_feeds(self):
                return  [
                ('This Week\'s Magazine', 'http://online.barrons.com/xml/rss/3_7510.xml'),
                ('Online Exclusives', 'http://online.barrons.com/xml/rss/3_7515.xml'),
                ('Companies', 'http://online.barrons.com/xml/rss/3_7516.xml'),
                ('Markets', 'http://online.barrons.com/xml/rss/3_7517.xml'),
                ('Technology', 'http://online.barrons.com/xml/rss/3_7518.xml'),
                ('Funds/Q&A', 'http://online.barrons.com/xml/rss/3_7519.xml'),
                ]

        ## Logout of website
        ## NOT CURRENTLY WORKING
        # def cleanup(self):
            # try:
                # self.browser.set_debug_responses(True)
                # import sys, logging
                # logger = logging.getLogger("mechanize")
                # logger.addHandler(logging.StreamHandler(sys.stdout))
                # logger.setLevel(logging.INFO)

                # res = self.browser.open('http://online.barrons.com/logout')
            # except:
                # import traceback
                # traceback.print_exc()



