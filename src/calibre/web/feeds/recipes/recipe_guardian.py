#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
www.guardian.co.uk
'''

from calibre.web.feeds.news import BasicNewsRecipe

class Guardian(BasicNewsRecipe):

    title = u'The Guardian'
    __author__ = 'Seabound and Sujata Raman'
    language = 'en_GB'

    oldest_article = 7
    max_articles_per_feed = 20
    remove_javascript = True

    timefmt = ' [%a, %d %b %Y]'
    keep_only_tags = [
                      dict(name='div', attrs={'id':["content","article_header","main-article-info",]}),
                           ]
    remove_tags = [
                        dict(name='div', attrs={'class':["video-content","videos-third-column"]}),
                        dict(name='div', attrs={'id':["article-toolbox","subscribe-feeds",]}),
                        dict(name='ul', attrs={'class':["pagination"]}),
                        dict(name='ul', attrs={'id':["content-actions"]}),
                        ]
    use_embedded_content    = False

    no_stylesheets = True
    extra_css = '''
                    .article-attributes{font-size: x-small; font-family:Arial,Helvetica,sans-serif;}
                    .h1{font-size: large ;font-family:georgia,serif; font-weight:bold;}
                    .stand-first-alone{color:#666666; font-size:small; font-family:Arial,Helvetica,sans-serif;}
                    .caption{color:#666666; font-size:x-small; font-family:Arial,Helvetica,sans-serif;}
                    #article-wrapper{font-size:small; font-family:Arial,Helvetica,sans-serif;font-weight:normal;}
                    .main-article-info{font-family:Arial,Helvetica,sans-serif;}
                    #full-contents{font-size:small; font-family:Arial,Helvetica,sans-serif;font-weight:normal;}
                    #match-stats-summary{font-size:small; font-family:Arial,Helvetica,sans-serif;font-weight:normal;}
                '''



    feeds = [
        ('Front Page', 'http://www.guardian.co.uk/rss'),
        ('Business', 'http://www.guardian.co.uk/business/rss'),
        ('Sport', 'http://www.guardian.co.uk/sport/rss'),
        ('Culture', 'http://www.guardian.co.uk/culture/rss'),
        ('Money', 'http://www.guardian.co.uk/money/rss'),
        ('Life & Style', 'http://www.guardian.co.uk/lifeandstyle/rss'),
        ('Travel', 'http://www.guardian.co.uk/travel/rss'),
        ('Environment', 'http://www.guardian.co.uk/environment/rss'),
        ('Comment','http://www.guardian.co.uk/commentisfree/rss'),
        ]

    def get_article_url(self, article):
          url = article.get('guid', None)
          if '/video/' in url or '/flyer/' in url or '/quiz/' in url or \
              '/gallery/' in url  or 'ivebeenthere' in url or \
              'pickthescore' in url or 'audioslideshow' in url :
              url = None
          return url



    def preprocess_html(self, soup):

          for item in soup.findAll(style=True):
              del item['style']

          for item in soup.findAll(face=True):
              del item['face']
          for tag in soup.findAll(name=['ul','li']):
                tag.name = 'div'

          return soup






