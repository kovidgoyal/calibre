##
##    web2lrf profile to download articles from WSJ.com 
##    can download subscriber-only content if username and  
##    password are supplied.
##
''' 
''' 
 
import re 
 
from libprs500.ebooks.lrf.web.profiles import DefaultProfile  
         
class WallStreetJournal(DefaultProfile): 
    
        title = 'Wall Street Journal' 
        max_recursions = 2
        needs_subscription = True 
        max_articles_per_feed = 50
        timefmt  = ' [%a, %b %d, %Y]' 
        html_description = True 
        no_stylesheets = False
        html2lrf_options = [('--ignore-tables')]

        ## Don't grab articles more than 7 days old 
        oldest_article = 7 
   
        preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in  
                [ 
                ## Remove anything before the body of the article. 
                (r'<body.*?<!-- article start', lambda match: '<body><!-- article start'), 
 
                ## Remove any insets from the body of the article. 
                (r'<div id="inset".*?</div>.?</div>.?<p', lambda match : '<p'), 
 
                ## Remove anything after the end of the article. 
                (r'<!-- article end.*?</body>', lambda match : '</body>'), 
                ] 
        ] 
 
        def get_browser(self): 
            br = DefaultProfile.get_browser() 
            if self.username is not None and self.password is not None: 
                br.open('http://online.wsj.com/login') 
                br.select_form(name='login_form') 
                br['user']   = self.username 
                br['password'] = self.password 
                br.submit() 
            return br 
 
        def print_version(self, url): 
                return url.replace('/article/', '/article_print/') 
 
## Comment out the feeds you don't want retrieved. 
## Because these feeds are sorted alphabetically when converted to LRF, you may want to number them  or use spaces to put them in the order you desire 
        def get_feeds(self): 
                return  [ 
                #('Most Emailed - Day', 'http://online.wsj.com/xml/rss/3_7030.xml'), 
                #('Most Emailed - Week', 'http://online.wsj.com/xml/rss/3_7253.xml'), 
                #('Most Emailed - Month', 'http://online.wsj.com/xml/rss/3_7254.xml'), 
                (' Most Viewed - Day', 'http://online.wsj.com/xml/rss/3_7198.xml'), 
                (' Most Viewed - Week', 'http://online.wsj.com/xml/rss/3_7251.xml'), 
                # ('Most Viewed - Month', 'http://online.wsj.com/xml/rss/3_7252.xml'), 
                ('  Today\'s Newspaper -  Page One', 'http://online.wsj.com/xml/rss/3_7205.xml'), 
                ('  Today\'s Newspaper - Marketplace', 'http://online.wsj.com/xml/rss/3_7206.xml'), 
                ('  Today\'s Newspaper - Money & Investing', 'http://online.wsj.com/xml/rss/3_7207.xml'), 
                ('  Today\'s Newspaper - Personal Journal', 'http://online.wsj.com/xml/rss/3_7208.xml'), 
                ('  Today\'s Newspaper - Weekend Journal', 'http://online.wsj.com/xml/rss/3_7209.xml'), 
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
                # ('Personal Journal - Gadgets', 'http://online.wsj.com/xml/rss/3_7094.xml'), 
                ('Weekend & Leisure', 'http://online.wsj.com/xml/rss/3_7201.xml'), 
                ('Weekend & Leisure - Weekend Journal', 'http://online.wsj.com/xml/rss/3_7202.xml'), 
                ('Weekend & Leisure - Arts & Entertainment', 'http://online.wsj.com/xml/rss/3_7177.xml'), 
                ('Weekend & Leisure - Books', 'http://online.wsj.com/xml/rss/3_7203.xml'), 
                # ('Weekend & Leisure - Travel', 'http://online.wsj.com/xml/rss/3_7106.xml'), 
                # ('Weekend & Leisure - Autos', 'http://online.wsj.com/xml/rss/3_7092.xml'), 
                ('Weekend & Leisure - Sports', 'http://online.wsj.com/xml/rss/3_7204.xml'), 
                ]

## Logout of website
## NOT CURRENTLY WORKING
        # def cleanup(self): 
            # self.browser.open('http://commerce.wsj.com/auth/postlogout') 
