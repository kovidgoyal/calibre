##  By Lorenzo goehr, lorenzogoehr@hotmail.com for Libprs500 by Kovid Goyal


from calibre.ebooks.lrf.web.profiles import DefaultProfile

import re

class NewYorkReviewOfBooks(DefaultProfile):

    title = 'New York Review of Books'
    max_recursions = 2
    max_articles_per_feed = 50
    html_description = True
    no_stylesheets = True
    
    def get_feeds(self):
        return [ ('Current Issue',  'http://feeds.feedburner.com/nybooks') ]

    preprocess_regexps = [(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in [
        (r'<meta http-equiv="Content-Type" content="text/html; charset=(\S+)"', lambda match : match.group().replace(match.group(1), 'UTF-8')),
        (r'<body.*?((<div id="article_body">)|(<div id="st-page-maincontent">)|(<div id="containermain">)|(<p class="ap-story-p">)|(<!-- img_nav -->))', lambda match: '<body><div>'),
        (r'((<!-- end article content -->)|(<div id="st-custom-afterpagecontent">)|(<p class="ap-story-p">&copy;)|(<div class="entry-footer">)|(<div id="see_also">)|(<p>Via <a href=)|(<div id="ss_nav">)).*?</html>', lambda match : '</div></body></html>'),
        (r'<div class="nav">.*?<h2>', lambda match: '<h2>'),
        (r'<table.*?>.*?(<img .*?/table>)', lambda match: match.group(1),), ] ]
