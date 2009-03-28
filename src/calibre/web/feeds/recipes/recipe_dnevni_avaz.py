#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'

'''
dnevniavaz.ba
'''

import re
from calibre.web.feeds.recipes import BasicNewsRecipe

class DnevniAvaz(BasicNewsRecipe):
    title                 = 'Dnevni Avaz'
    __author__            = 'Darko Miletic'
    description           = 'Latest news from Bosnia'
    publisher             = 'Dnevni Avaz'
    category              = 'news, politics, Bosnia and Herzegovina'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    encoding              = 'utf-8'
    use_embedded_content  = False
    remove_javascript     = True
    cover_url             = 'http://www.dnevniavaz.ba/img/logo.gif'
    lang                  = 'bs-BA'
    language              = _('Bosnian')

    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: serif1, serif}'

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\noverride_css=" p {text-indent: 0em; margin-top: 0em; margin-bottom: 0.5em} img {margin-top: 0em; margin-bottom: 0.4em}"'

    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]

    keep_only_tags = [dict(name='div', attrs={'id':['fullarticle-title','fullarticle-leading','fullarticle-date','fullarticle-text','articleauthor']})]

    remove_tags = [dict(name=['object','link','base'])]

    feeds = [
               (u'Najnovije'     , u'http://www.dnevniavaz.ba/rss/novo'     )
              ,(u'Najpopularnije', u'http://www.dnevniavaz.ba/rss/popularno')
            ]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Language" content="bs-BA"/>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        soup.head.insert(0,mtag)
        return soup
