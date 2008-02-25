
import re, time
from libprs500.ebooks.lrf.web.profiles import DefaultProfile
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

class ChristianScienceMonitor(DefaultProfile):

    title = 'Christian Science Monitor'
    max_recursions = 2
    max_articles_per_feed = 20
    no_stylesheets = True
    
  

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
        [
        (r'<body.*?<div id="story"', lambda match : '<body><div id="story"'),
        (r'<div class="pubdate">.*?</div>', lambda m: ''),
        (r'Full HTML version of this story which may include photos, graphics, and related links.*</body>',
              lambda match : '</body>'),
        ]]
     

    def parse_feeds(self):
        soup = BeautifulSoup(self.browser.open('http://www.csmonitor.com/textedition'))
        articles = {}
        feed = []
        for tag in soup.findAll(['h2', 'p']):
            if tag.name == 'h2':
                title = self.tag_to_string(tag)
                feed = [] 
                articles[title] = feed
            elif tag.has_key('class') and tag['class'] == 'story':
                a = tag.find('a')
                if a is not None and a.has_key('href'):
                    feed.append({
                         'title': self.tag_to_string(a),
                         'url'  : 'http://www.csmonitor.com'+a['href'],
                         'date' : time.strftime('%d %b'),
                         'content' : '',
                         })
                    a.extract()
                    feed[-1]['description'] = self.tag_to_string(tag).strip()
        return articles
      
