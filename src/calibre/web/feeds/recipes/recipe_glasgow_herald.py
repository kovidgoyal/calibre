import re

from calibre.web.feeds.news import BasicNewsRecipe

class GlasgowHerald(BasicNewsRecipe):
    title          = u'Glasgow Herald'
    oldest_article = 1
    max_articles_per_feed = 100
    no_stylesheets = True
    language = 'en'

    __author__     = 'McCande' 

    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
    [
                (r'<center><h3>', lambda match : '<h3>'),
                (r'Click here to comment on this story...', lambda match : ''),
                (r'<h3>Related links</h3>.*?</head>', lambda match : '</head>'),
        ]
        ]




    feeds          = [
                        (u'News', u'http://www.theherald.co.uk/news/news/rss.xml'),
                        (u'Politics', u'http://www.theherald.co.uk/politics/news/rss.xml'),
                        (u'Features', u'http://www.theherald.co.uk/features/features/rss.xml'),
                        (u'Business', u'http://www.theherald.co.uk/business/news/rss.xml')]

    def print_version(self, url):
        (beginning,end)=url.split(".var.")
        num=end[0:7]
        main="http://www.theherald.co.uk/misc/print.php?artid="+num
        return main
