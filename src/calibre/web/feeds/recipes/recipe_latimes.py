#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
latimes.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class LATimes(BasicNewsRecipe):
    title                 = u'The Los Angeles Times'
    __author__            = u'Darko Miletic and Sujata Raman'
    description           = u'News from Los Angeles'
    oldest_article        = 7
    max_articles_per_feed = 100
    language              = 'en'
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf-8'
    lang                  = 'en-US'

    conversion_options = {
          'comment'          : description
        , 'language'         : lang
    }

    extra_css = '''
                h1{font-family :Georgia,"Times New Roman",Times,serif; font-size:large; }
                h2{font-family :Georgia,"Times New Roman",Times,serif; font-size:x-small;}
                .story{font-family :Georgia,"Times New Roman",Times,serif; font-size: x-small;}
                .entry-body{font-family :Georgia,"Times New Roman",Times,serif; font-size: x-small;}
                .entry-more{font-family :Georgia,"Times New Roman",Times,serif; font-size: x-small;}
                .credit{color:#666666; font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;}
                .small{color:#666666; font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;}
                .byline{font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;}
                .date{font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;color:#930000; font-style:italic;}
                .time{font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;color:#930000; font-style:italic;}
                .copyright{font-family :Georgia,"Times New Roman",Times,serif; font-size: xx-small;color:#930000; }
                .subhead{font-family :Georgia,"Times New Roman",Times,serif; font-size:x-small;}
                '''

   # recursions = 1
   # match_regexps = [r'http://www.latimes.com/.*page=[2-9]']

    keep_only_tags    = [dict(name='div', attrs={'class':["story"  ,"entry"] })]


    remove_tags      = [   dict(name='div', attrs={'class':['articlerail',"sphereTools","tools","toppaginate","entry-footer-left","entry-footer-right"]}),
                            dict(name='div', attrs={'id':["moduleArticleToolsContainer",]}),
                            dict(name='p', attrs={'class':["entry-footer",]}),
                           dict(name='ul', attrs={'class':"article-nav clearfix"}),
                            dict(name=['iframe'])
                        ]


    feeds          = [(u'News', u'http://feeds.latimes.com/latimes/news')
                      ,(u'Local','http://feeds.latimes.com/latimes/news/local')
                      ,(u'MostEmailed','http://feeds.latimes.com/MostEmailed')
                      ,(u'Politics','http://feeds.latimes.com/latimes/news/local/politics/cal/')
                      ,('OrangeCounty','http://feeds.latimes.com/latimes/news/local/orange/')
                      ,('National','http://feeds.latimes.com/latimes/news/nationworld/nation')
                      ,('Politics','http://feeds.latimes.com/latimes/news/politics/')
                      ,('Business','http://feeds.latimes.com/latimes/business')
                      ,('Sports','http://feeds.latimes.com/latimes/sports/')
                      ,('Entertainment','http://feeds.latimes.com/latimes/entertainment/')
                      ]


    def get_article_url(self, article):
        ans = article.get('feedburner_origlink').rpartition('?')[0]

        try:
            self.log('Looking for full story link in', ans)
            soup = self.index_to_soup(ans)
            x = soup.find(text="single page")

            if x is not None:
                a = x.parent
                if a and a.has_key('href'):
                    ans = 'http://www.latimes.com'+a['href']
                    self.log('Found full story link', ans)
        except:
            pass
        return ans


