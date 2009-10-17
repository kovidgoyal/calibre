__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Hessisch Niedersachsische Allgemeine.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class hnaDe(BasicNewsRecipe):

    title = 'HNA'
    description = 'local news from Hessen/Germany'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    language = 'de'

    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    remove_javascript = True
    encoding = 'iso-8859-1'

    remove_tags = [dict(id='topnav'),
		   dict(id='nav_main'),
		   dict(id='teaser'),
		   dict(id='suchen'),
		   dict(id='superbanner'),
		   dict(id='navigation'),
		   dict(id='skyscraper'),
		   dict(id=''),
                   dict(name='span'),
		   dict(name='ul', attrs={'class':'linklist'}),
		   dict(name='a', attrs={'href':'#'}),
		   dict(name='div', attrs={'class':'hlist'}),
		   dict(name='div', attrs={'class':'subc noprint'}),
		   dict(name='p', attrs={'class':'breadcrumb'}),
		   dict(name='a', attrs={'style':'cursor:hand'}),
		   dict(name='p', attrs={'class':'h5'})]
    #remove_tags_after = [dict(name='div', attrs={'class':'rahmenbreaking'})]
    remove_tags_after = [dict(name='a', attrs={'href':'#'})]

    feeds =  [ ('hna_soehre', 'http://feeds2.feedburner.com/hna/soehre'),
	       ('hna_kassel', 'http://feeds2.feedburner.com/hna/kassel') ]




