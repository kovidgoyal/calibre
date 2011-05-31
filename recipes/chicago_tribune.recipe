from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.web.feeds.news import BasicNewsRecipe

class ChicagoTribune(BasicNewsRecipe):

    title       = 'Chicago Tribune'
    __author__  = 'Kovid Goyal and Sujata Raman'
    description = 'Politics, local and business news from Chicago'
    language = 'en'

    use_embedded_content    = False
    no_stylesheets        = True
    remove_javascript = True

    keep_only_tags = [dict(name='div', attrs={'class':["story","entry-asset asset hentry"]}),
                      dict(name='div', attrs={'id':["pagebody","story","maincontentcontainer"]}),
                           ]
    remove_tags_after = [    {'class':['photo_article',]} ]

    remove_tags = [{'id':["moduleArticleTools","content-bottom","rail","articleRelates module","toolSet","relatedrailcontent","div-wrapper","beta","atp-comments","footer"]},
                   {'class':["clearfix","relatedTitle","articleRelates module","asset-footer","tools","comments","featurePromo","featurePromo fp-topjobs brownBackground","clearfix fullSpan brownBackground","curvedContent"]},
                   dict(name='font',attrs={'id':["cr-other-headlines"]})]
    extra_css = '''
                    h1{font-family:Arial,Helvetica,sans-serif; font-weight:bold;font-size:large;}
                    h2{font-family:Arial,Helvetica,sans-serif; font-weight:normal;font-size:small;}
                    .byline {font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                    .date {font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                    p{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    .copyright {font-family:Arial,Helvetica,sans-serif;font-size:xx-small;text-align:center}
                    .story{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    .entry-asset asset hentry{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    .pagebody{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    .maincontentcontainer{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    .story-body{font-family:Arial,Helvetica,sans-serif;font-size:small;}
                    body{font-family:Helvetica,Arial,sans-serif;font-size:small;}
		'''
    feeds = [
             ('Latest news', 'http://feeds.chicagotribune.com/chicagotribune/news/'),
             ('Local news', 'http://feeds.chicagotribune.com/chicagotribune/news/local/'),
             ('Nation/world', 'http://feeds.chicagotribune.com/chicagotribune/news/nationworld/'),
             ('Hot topics', 'http://feeds.chicagotribune.com/chicagotribune/hottopics/'),
             ('Most E-mailed stories', 'http://feeds.chicagotribune.com/chicagotribune/email/'),
             ('Opinion', 'http://feeds.chicagotribune.com/chicagotribune/opinion/'),
             ('Off Topic', 'http://feeds.chicagotribune.com/chicagotribune/offtopic/'),
             #('Politics', 'http://feeds.chicagotribune.com/chicagotribune/politics/'),
             #('Special Reports', 'http://feeds.chicagotribune.com/chicagotribune/special/'),
             #('Religion News', 'http://feeds.chicagotribune.com/chicagotribune/religion/'),
             ('Business news', 'http://feeds.chicagotribune.com/chicagotribune/business/'),
             ('Jobs and Careers', 'http://feeds.chicagotribune.com/chicagotribune/career/'),
             ('Local scene', 'http://feeds.chicagotribune.com/chicagohomes/localscene/'),
             ('Phil Rosenthal', 'http://feeds.chicagotribune.com/chicagotribune/rosenthal/'),
             #('Tech Buzz', 'http://feeds.chicagotribune.com/chicagotribune/techbuzz/'),
             ('Your Money', 'http://feeds.chicagotribune.com/chicagotribune/yourmoney/'),
             ('Jon Hilkevitch - Getting around', 'http://feeds.chicagotribune.com/chicagotribune/gettingaround/'),
             ('Jon Yates - What\'s your problem?', 'http://feeds.chicagotribune.com/chicagotribune/problem/'),
             ('Garisson Keillor', 'http://feeds.chicagotribune.com/chicagotribune/keillor/'),
             ('Marks Jarvis - On Money', 'http://feeds.chicagotribune.com/chicagotribune/marksjarvisonmoney/'),
             ('Sports', 'http://feeds.chicagotribune.com/chicagotribune/sports/'),
             ('Arts and Architecture', 'http://feeds.chicagotribune.com/chicagotribune/arts/'),
             ('Books', 'http://feeds.chicagotribune.com/chicagotribune/books/'),
             #('Magazine', 'http://feeds.chicagotribune.com/chicagotribune/magazine/'),
             ('Movies', 'http://feeds.chicagotribune.com/chicagotribune/movies/'),
             ('Music', 'http://feeds.chicagotribune.com/chicagotribune/music/'),
             ('TV', 'http://feeds.chicagotribune.com/chicagotribune/tv/'),
             ('Hypertext', 'http://feeds.chicagotribune.com/chicagotribune/hypertext/'),
             ('iPhone Blog', 'http://feeds.feedburner.com/redeye/iphoneblog'),
             ('Julie\'s Health Club', 'http://feeds.chicagotribune.com/chicagotribune_julieshealthclub/'),
             ]


    def get_article_url(self, article):
        print article.get('feedburner_origlink', article.get('guid', article.get('link')))
        return article.get('feedburner_origlink', article.get('guid', article.get('link')))


    def postprocess_html(self, soup, first_fetch):
        for t in soup.findAll(['table', 'tr', 'td']):
            t.name = 'div'

        for tag in soup.findAll('form', dict(attrs={'name':["comments_form"]})):
            tag.extract()
        for tag in soup.findAll('font', dict(attrs={'id':["cr-other-headlines"]})):
            tag.extract()

        return soup


