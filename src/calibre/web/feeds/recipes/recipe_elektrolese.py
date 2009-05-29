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
    language = _('German')
    oldest_article = 14
    max_articles_per_feed = 50
    no_stylesheets = True
    #html2epub_options = 'linearize_tables = True\nbase_font_size2=14'
    encoding = 'utf-8'


    remove_tags_after = [dict(id='comments')]
    filter_regexps = [r'ad\.doubleclick\.net']

    remove_tags = [dict(name='div', attrs={'class':'bannerSuperBanner'}),
                   dict(id='comments')]



    feeds =  [ (u'electrolese', u'http://elektrolese.blogspot.com/feeds/posts/default?alt=rss') ]

