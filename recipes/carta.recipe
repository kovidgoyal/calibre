__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Carta.info.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class Carta(BasicNewsRecipe):

    title = u'Carta'
    description = 'News about electronic publishing'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%a %d %b %Y]'
    oldest_article = 7
    max_articles_per_feed = 50
    no_stylesheets = True
    remove_javascript = True
    #html2epub_options = 'linearize_tables = True\nbase_font_size2=14'
    encoding = 'utf-8'
    language = 'de'



    remove_tags_after = [dict(name='p', attrs={'class':'tags-blog'})]

    remove_tags = [dict(name='p', attrs={'class':'print'}),
                   dict(name='p', attrs={'class':'tags-blog'}),
                   dict(name='p', attrs={'class':'mail'}),
                   dict(name='p', attrs={'style':'text-align: center;'}),
                   dict(name='p', attrs={'align':'left'}),
                   dict(name='p', attrs={'class':'date'}),
                   dict(id='comments'),
                   dict(id='headerleft'),
                   dict(id='subnav'),
                   dict(id='headerright')]


    feeds =  [ (u'Carta', u'http://feeds2.feedburner.com/carta-standard-rss') ]


    def print_version(self, url):
        return url + 'print/'
