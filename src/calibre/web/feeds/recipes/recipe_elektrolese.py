__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch elektrolese.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class elektrolese(BasicNewsRecipe):

    title = u'elektrolese'
    description = 'News about electronic publishing'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%a %d %b %Y]'
    language = 'de'

    oldest_article = 14
    max_articles_per_feed = 50
    no_stylesheets = True
    conversion_options = {'linearize_tables':True}
    encoding = 'utf-8'


    remove_tags_after = [dict(id='comments')]
    filter_regexps = [r'ad\.doubleclick\.net']

    remove_tags = [dict(name='div', attrs={'class':'bannerSuperBanner'}),
                   dict(id='comments'),
                   dict(id='Navbar1')]



    feeds =  [ (u'elektrolese', u'http://elektrolese.blogspot.com/feeds/posts/default?alt=rss') ]


