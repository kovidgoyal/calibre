__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch zdnet.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class cdnet(BasicNewsRecipe):

    title = 'zdnet'
    description = 'zdnet security'
    __author__ = 'Oliver Niesner'
    language = 'en'

    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    encoding = 'latin1'



    remove_tags = [dict(id='eyebrows'),
		   dict(id='header'),
		   dict(id='search'),
		   dict(id='nav'),
		   dict(id=''),
		   dict(name='div', attrs={'class':'banner'}),
		   dict(name='p', attrs={'class':'tags'}),
		   dict(name='a', attrs={'href':'http://www.twitter.com/ryanaraine'}),
		   dict(name='div', attrs={'class':'special1'})]
    remove_tags_after = [dict(name='div', attrs={'class':'bloggerDesc clear'})]

    feeds =  [ ('zdnet', 'http://feeds.feedburner.com/zdnet/security') ]


    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return soup


