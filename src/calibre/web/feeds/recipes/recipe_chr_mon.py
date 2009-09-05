
import re
from calibre.web.feeds.news import BasicNewsRecipe

class ChristianScienceMonitor(BasicNewsRecipe):

    title = 'Christian Science Monitor'
    description = 'Providing context and clarity on national and international news, peoples and cultures'
    max_articles_per_feed = 20
    __author__ = 'Kovid Goyal'
    language = 'en'

    no_stylesheets = True
    use_embedded_content   = False
  

    
    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in 
        [
        (r'<body.*?<div id="story"', lambda match : '<body><div id="story"'),
        (r'<div class="pubdate">.*?</div>', lambda m: ''),
        (r'Full HTML version of this story which may include photos, graphics, and related links.*</body>',
              lambda match : '</body>'),
        ]]
     

    def parse_index(self):
        soup = self.index_to_soup('http://www.csmonitor.com/textedition')
        feeds = []
        for tag in soup.findAll(['h2', 'p']):
            if tag.name == 'h2':
                title = self.tag_to_string(tag)
                feeds.append((title, []))
            elif tag.has_key('class') and tag['class'] == 'story' and feeds:
                a = tag.find('a')
                if a is not None and a.has_key('href'):
                    art = {
                         'title': self.tag_to_string(a),
                         'url'  : 'http://www.csmonitor.com'+a['href'],
                         'date' : '',
                         }
                    a.extract()
                    art['description'] = self.tag_to_string(tag).strip()
                    feeds[-1][1].append(art)
        return feeds
      
    def postprocess_html(self, soup, first_fetch):
        html = soup.find('html')
        if html is None:
            return soup
        html.extract()
        return html
