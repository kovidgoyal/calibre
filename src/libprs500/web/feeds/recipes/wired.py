#!/usr/bin/env  python
__license__   = 'GPL v3'
__docformat__ = 'restructuredtext en'

import re

from libprs500.web.feeds.news import BasicNewsRecipe

class Wired(BasicNewsRecipe):
    
    title = 'Wired.com'
    __author__ = 'David Chen <SonyReader<at>DaveChen<dot>org>'
    description = 'Technology news'
    timefmt  = ' [%Y%b%d  %H%M]'
    no_stylesheets = True
    html2lrf_options = ['--base-font-size', '16']
    
    preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
  
                [
  
                ## Remove any banners/links/ads/cruft before the body of the article.
                (r'<body.*?((<div id="article_body">)|(<div id="st-page-maincontent">)|(<div id="containermain">)|(<p class="ap-story-p">)|(<!-- img_nav -->))', lambda match: '<body><div>'),
  
                ## Remove any links/ads/comments/cruft from the end of the body of the article.
                (r'((<!-- end article content -->)|(<div id="st-custom-afterpagecontent">)|(<p class="ap-story-p">&copy;)|(<div class="entry-footer">)|(<div id="see_also">)|(<p>Via <a href=)|(<div id="ss_nav">)).*?</html>', lambda match : '</div></body></html>'),
  
                ## Correctly embed in-line images by removing the surrounding javascript that will be ignored in the conversion
                (r'<a.*?onclick.*?>.*?(<img .*?>)', lambda match: match.group(1),),
                
                ]
            ]
    
    feeds = [
        ('Top News', 'http://feeds.wired.com/wired/index'),
        ('Culture', 'http://feeds.wired.com/wired/culture'),
        ('Software', 'http://feeds.wired.com/wired/software'),
        ('Mac', 'http://feeds.feedburner.com/cultofmac/bFow'),
        ('Gadgets', 'http://feeds.wired.com/wired/gadgets'),
        ('Cars', 'http://feeds.wired.com/wired/cars'),
        ('Entertainment', 'http://feeds.wired.com/wired/entertainment'),
        ('Gaming', 'http://feeds.wired.com/wired/gaming'),
        ('Science', 'http://feeds.wired.com/wired/science'),
        ('Med Tech', 'http://feeds.wired.com/wired/medtech'),
        ('Politics', 'http://feeds.wired.com/wired/politics'),
        ('Tech Biz', 'http://feeds.wired.com/wired/techbiz'),
        ('Commentary', 'http://feeds.wired.com/wired/commentary'),
        ]
    
    def print_version(self, url):
        return url.replace('http://www.wired.com/', 'http://www.wired.com/print/')
    
    