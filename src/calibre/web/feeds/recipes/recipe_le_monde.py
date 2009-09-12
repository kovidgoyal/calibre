#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Mathieu Godlewski <mathieu at godlewski.fr>'
'''
lemonde.fr
'''

import re
#from datetime import date
from calibre.web.feeds.news import BasicNewsRecipe


class LeMonde(BasicNewsRecipe):
    title          = 'LeMonde.fr'
    __author__ = 'Mathieu Godlewski <mathieu at godlewski.fr>'
    description = 'Global news in french'
    oldest_article = 3
    language = 'fr'

    max_articles_per_feed = 30
    no_stylesheets = True
    remove_javascript = True


    #cover_url='http://abonnes.lemonde.fr/titresdumonde/'+date.today().strftime("%y%m%d")+'/1.jpg'


    extra_css = '''
                    .dateline{color:#666666;font-family:verdana,sans-serif;font-size:xx-small;}
                    .mainText{font-family:Georgia,serif;color:#222222;}
                    .LM_articleText{font-family:Georgia,serif;}
                    .mainContent{font-family:Georgia,serif;}
                    .mainTitle{font-family:Georgia,serif;}
                    .LM_content{font-family:Georgia,serif;}
                    .content{font-family:Georgia,serif;}
                    .LM_caption{font-family:Georgia,serif;font-size:xx-small;}
                    .LM_imageSource{font-family:Arial,Helvetica,sans-serif;font-size:xx-small;color:#666666;}
                    h1{font-family:Georgia,serif;font-size:medium;color:#000000;}
                    .entry{font-family:Georgia,Times New Roman,Times,serif;}
                    .mainTitle{font-family:Georgia,Times New Roman,Times,serif;}
                    h2{font-family:Georgia,Times New Roman,Times,serif;font-size:large;}
                    small{{font-family:Arial,Helvetica,sans-serif;font-size:xx-small;}
                '''

    feeds =  [
             ('A la Une', 'http://www.lemonde.fr/rss/une.xml'),
             ('International', 'http://www.lemonde.fr/rss/sequence/0,2-3210,1-0,0.xml'),
             ('Europe', 'http://www.lemonde.fr/rss/sequence/0,2-3214,1-0,0.xml'),
             ('Societe', 'http://www.lemonde.fr/rss/sequence/0,2-3224,1-0,0.xml'),
             ('Economie', 'http://www.lemonde.fr/rss/sequence/0,2-3234,1-0,0.xml'),
             ('Medias', 'http://www.lemonde.fr/rss/sequence/0,2-3236,1-0,0.xml'),
             ('Rendez-vous', 'http://www.lemonde.fr/rss/sequence/0,2-3238,1-0,0.xml'),
             ('Sports', 'http://www.lemonde.fr/rss/sequence/0,2-3242,1-0,0.xml'),
             ('Planete', 'http://www.lemonde.fr/rss/sequence/0,2-3244,1-0,0.xml'),
             ('Culture', 'http://www.lemonde.fr/rss/sequence/0,2-3246,1-0,0.xml'),
             ('Technologies', 'http://www.lemonde.fr/rss/sequence/0,2-651865,1-0,0.xml'),
             ('Cinema', 'http://www.lemonde.fr/rss/sequence/0,2-3476,1-0,0.xml'),
             ('Voyages', 'http://www.lemonde.fr/rss/sequence/0,2-3546,1-0,0.xml'),
             ('Livres', 'http://www.lemonde.fr/rss/sequence/0,2-3260,1-0,0.xml'),
             ('Examens', 'http://www.lemonde.fr/rss/sequence/0,2-3404,1-0,0.xml'),
             ('Opinions', 'http://www.lemonde.fr/rss/sequence/0,2-3232,1-0,0.xml')
             ]
    keep_only_tags = [dict(name='div', attrs={'id':["mainTitle","mainContent","LM_content","content"]}),
                      dict(name='div', attrs={'class':["post"]})
                      ]

    remove_tags    = [dict(name='img', attrs={'src':'http://medias.lemonde.fr/mmpub/img/lgo/lemondefr_pet.gif'}),
                                    dict(name='div', attrs={'id':'xiti-logo-noscript'}),
                                    dict(name='br', attrs={}),
                                    dict(name='iframe', attrs={}),
                     dict(name='table', attrs={'id':["toolBox"]}),
                      dict(name='table', attrs={'class':["bottomToolBox"]}),
                      dict(name='div', attrs={'class':["pageNavigation","fenetreBoxesContainer","breakingNews","LM_toolsBottom","LM_comments","LM_tools","pave_meme_sujet_hidden","boxMemeSujet"]}),
                      dict(name='div', attrs={'id':["miniUne","LM_sideBar"]}),
    ]


    preprocess_regexps = [ (re.compile(i[0], re.IGNORECASE|re.DOTALL), i[1]) for i in
        [
            (r'<html.*(<div class="post".*?>.*?</div>.*?<div class="entry">.*?</div>).*You can start editing here.*</html>', lambda match : '<html><body>'+match.group(1)+'</body></html>'),
            (r'<p>&nbsp;</p>', lambda match : ''),
            (r'<img src="http://medias\.lemonde\.fr/mmpub/img/let/(.)\.gif"[^>]*><div class=ar-txt>', lambda match : '<div class=ar-txt>'+match.group(1).upper()),
            (r'<img src="http://medias\.lemonde\.fr/mmpub/img/let/q(.)\.gif"[^>]*><div class=ar-txt>', lambda match : '<div class=ar-txt>"'+match.group(1).upper()),
            (r'(<div class=desc><b>.*</b></div>).*</body>', lambda match : match.group(1)),
        ]
    ]

    article_match_regexps = [ (re.compile(i)) for i in
        [
            (r'http://www\.lemonde\.fr/\S+/article/.*'),
            (r'http://www\.lemonde\.fr/\S+/portfolio/.*'),
            (r'http://www\.lemonde\.fr/\S+/article_interactif/.*'),
            (r'http://\S+\.blog\.lemonde\.fr/.*'),
        ]
    ]

   # def print_version(self, url):
   #     return re.sub('http://www\.lemonde\.fr/.*_([0-9]+)_[0-9]+\.html.*','http://www.lemonde.fr/web/imprimer_element/0,40-0,50-\\1,0.html' ,url)

    # Used to filter duplicated articles
    articles_list = []

    def get_article_url(self, article):
        url=article.get('link',  None)
        url=url[0:url.find("#")]
        if url in self.articles_list:
            self.log_debug(_('Skipping duplicated article: %s')%url)
            return False
        if self.is_article_wanted(url):
            self.articles_list.append(url)
            return url
        self.log_debug(_('Skipping filtered article: %s')%url)
        return False


    def is_article_wanted(self, url):
        if self.article_match_regexps:
            for m in self.article_match_regexps:
                if m.search(url):
                    return True
            return False
        return False


