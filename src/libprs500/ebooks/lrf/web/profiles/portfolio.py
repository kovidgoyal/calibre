##
##    web2lrf profile to download articles from Portfolio.com 
##
''' 
''' 
 
from libprs500.ebooks.lrf.web.profiles import FullContentProfile  
         
class Portfolio(FullContentProfile): 
    
        title = 'Portfolio'
        max_articles_per_feed = 50
        timefmt  = ' [%a, %b %d, %Y]' 
        html_description = True 
        no_stylesheets = True
        html2lrf_options = ['--ignore-tables']
        ##delay = 1
        
        oldest_article = 30

## Comment out the feeds you don't want retrieved. 
## Because these feeds are sorted alphabetically when converted to LRF, you may want to number them or use spaces to put them in the order you desire 
        def get_feeds(self): 
                return  [ 
                ('Business Travel', 'http://feeds.portfolio.com/portfolio/businesstravel'), 
                ('Careers', 'http://feeds.portfolio.com/portfolio/careers'), 
                ('Culture and Lifestyle', 'http://feeds.portfolio.com/portfolio/cultureandlifestyle'), 
                ('Executives','http://feeds.portfolio.com/portfolio/executives'), 
                ('News and Markets', 'http://feeds.portfolio.com/portfolio/news'), 
                ('Business Spin', 'http://feeds.portfolio.com/portfolio/businessspin'), 
                ('Capital', 'http://feeds.portfolio.com/portfolio/capital'), 
                ('Daily Brief', 'http://feeds.portfolio.com/portfolio/dailybrief'), 
                ('Market Movers', 'http://feeds.portfolio.com/portfolio/marketmovers'), 
                ('Mixed Media', 'http://feeds.portfolio.com/portfolio/mixedmedia'), 
                ('Odd Numbers', 'http://feeds.portfolio.com/portfolio/oddnumbers'), 
                ('Playbook', 'http://feeds.portfolio.com/portfolio/playbook'), 
                ('Tech Observer', 'http://feeds.portfolio.com/portfolio/thetechobserver'), 
                ('World According to ...', 'http://feeds.portfolio.com/portfolio/theworldaccordingto'), 
                ]

