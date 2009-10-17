import re
from calibre.web.feeds.news import BasicNewsRecipe

class Cyberpresse(BasicNewsRecipe):

    title          = u'Cyberpresse'
    __author__     = 'balok'
    description    = 'Canadian news in French'
    language = 'fr'

    oldest_article = 7
    max_articles_per_feed = 100
    no_stylesheets = True
    html2lrf_options = ['--left-margin=0','--right-margin=0','--top-margin=0','--bottom-margin=0']
    
    preprocess_regexps = [
    	 (re.compile(r'<body.*?<!-- END .centerbar -->', re.IGNORECASE | re.DOTALL), lambda match : '<BODY>'),
    	 (re.compile(r'<!-- END .entry -->.*?</body>', re.IGNORECASE | re.DOTALL), lambda match : '</BODY>'),
           (re.compile(r'<strong>Agrandir.*?</strong>', re.IGNORECASE | re.DOTALL), lambda match : '<br>'),   
   ] 


    feeds          = [(u'Manchettes', u'http://www.cyberpresse.ca/rss/225.xml'),(u'Capitale nationale', u'http://www.cyberpresse.ca/rss/501.xml'),(u'Opinions', u'http://www.cyberpresse.ca/rss/977.xml'),(u'Insolite', u'http://www.cyberpresse.ca/rss/279.xml')]

