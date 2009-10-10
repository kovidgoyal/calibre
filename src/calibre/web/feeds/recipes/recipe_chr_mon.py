
import re
from calibre import strftime
from calibre.web.feeds.news import BasicNewsRecipe

class ChristianScienceMonitor(BasicNewsRecipe):

    title = 'Christian Science Monitor'
    description = 'Providing context and clarity on national and international news, peoples and cultures'
    max_articles_per_feed = 20
    __author__ = 'Kovid Goyal and Sujata Raman'
    language = 'en'
    encoding = 'utf-8'
    no_stylesheets = True
    use_embedded_content   = False



    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
        [
        (r'<body.*?<div id="story"', lambda match : '<body><div id="story"'),
        (r'<div class="pubdate">.*?</div>', lambda m: ''),
        (r'Full HTML version of this story which may include photos, graphics, and related links.*</body>',
              lambda match : '</body>'),
        ]]

    extra_css      = '''
                        h1{ color:#000000;font-family: Georgia,Times,"Times New Roman",serif; font-size: large}
                        .sub{ color:#000000;font-family: Georgia,Times,"Times New Roman",serif; font-size: small;}
                        .byline{ font-family:Arial,Helvetica,sans-serif ; color:#999999; font-size: x-small;}
                        .postdate{color:#999999 ;  font-family:Arial,Helvetica,sans-serif ; font-size: x-small; }
                        h3{color:#999999 ;  font-family:Arial,Helvetica,sans-serif ; font-size: x-small; }
                        .photoCutline{ color:#333333 ; font-family:Arial,Helvetica,sans-serif ; font-size: x-small; }
                        .photoCredit{ color:#999999 ; font-family:Arial,Helvetica,sans-serif ; font-size: x-small; }
                        #story{font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; font-size: small; }
                        #main{font-family:Arial,Tahoma,Verdana,Helvetica,sans-serif ; font-size: small; }
                        #photo-details{ font-family:Arial,Helvetica,sans-serif ; color:#999999; font-size: x-small;}
                        span.name{color:#205B87;font-family: Georgia,Times,"Times New Roman",serif; font-size: x-small}
                        p#dateline{color:#444444 ;  font-family:Arial,Helvetica,sans-serif ; font-style:italic;}
                        '''
    feeds          = [
                        (u'Top Stories' , u'http://rss.csmonitor.com/feeds/top'),
                        (u'World' , u'http://rss.csmonitor.com/feeds/world'),
                        (u'USA' , u'http://rss.csmonitor.com/feeds/usa'),
                        (u'Commentary' , u'http://rss.csmonitor.com/feeds/commentary'),
                        (u'Money' , u'http://rss.csmonitor.com/feeds/wam'),
                        (u'Learning' , u'http://rss.csmonitor.com/feeds/learning'),
                        (u'Living', u'http://rss.csmonitor.com/feeds/living'),
                        (u'Innovation', u'http://rss.csmonitor.com/feeds/scitech'),
                        (u'Gardening', u'http://rss.csmonitor.com/feeds/gardening'),
                        (u'Environment',u'http://rss.csmonitor.com/feeds/environment'),
                        (u'Arts', u'http://rss.csmonitor.com/feeds/arts'),
                        (u'Books', u'http://rss.csmonitor.com/feeds/books'),
                        (u'Home Forum' , u'http://rss.csmonitor.com/feeds/homeforum')
                     ]

    keep_only_tags = [
                        dict(name='div', attrs={'id':['story','main']}),
                        ]

    remove_tags    = [
                        dict(name='div', attrs={'id':['story-tools','videoPlayer','storyRelatedBottom','enlarge-photo','photo-paginate']}),
                        dict(name='div', attrs={'class':[ 'spacer3','divvy spacer7','comment','storyIncludeBottom']}),
                        dict(name='ul', attrs={'class':[ 'centerliststories']}) ,
                        dict(name='form', attrs={'id':[ 'commentform']}) ,
                    ]


    def find_articles(self, section):
        ans = []
        for x in section.findAll('head4'):
            title = ' '.join(x.findAll(text=True)).strip()
            a = x.find('a')
            if not a: continue
            href = a['href']
            ans.append({'title':title, 'url':href, 'description':'', 'date': strftime('%a, %d %b')})

        #for x in ans:
        #    x['url'] += '/output/print'
        return ans

    def postprocess_html(self, soup, first_fetch):
        html = soup.find('html')
        if html is None:
            return soup
        html.extract()
        return html
