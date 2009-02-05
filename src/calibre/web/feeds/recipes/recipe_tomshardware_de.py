__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch tomshardware.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class TomsHardwareDe(BasicNewsRecipe):
    
    title = 'Tom\'s Hardware German'
    description = 'Computer news in german'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 50
    language = _('German')
    no_stylesheets = True
    encoding = 'utf-8'

    #preprocess_regexps = \
#	[(re.compile(i[0], re.IGNORECASE | re.DOTALL), i[1]) for i in
#		[
#		(r'<84>', lambda match: ''),
#		(r'<93>', lambda match: ''),
#		]
#	]
    
    remove_tags = [dict(id='outside-advert'),
		   dict(id='advertRightWhite'),
		   dict(id='header-advert'),
		   dict(id='header-banner'),
		   dict(id='header-menu'),
		   dict(id='header-top'),
		   dict(id='header-tools'),
		   dict(id='nbComment'),
		   dict(id='internalSidebar'),
		   dict(id='header-news-infos'),
		   dict(id='breadcrumbs'),
		   dict(id=''),
		   dict(name='div', attrs={'class':'pyjama'}),
		   dict(name='href', attrs={'class':'comment'}),
		   dict(name='div', attrs={'class':'greyBoxR clearfix'}),
		   dict(name='div', attrs={'class':'greyBoxL clearfix'}),
		   dict(name='div', attrs={'class':'greyBox clearfix'}),
		   dict(id='')]
    #remove_tags_before = [dict(id='header-news-title')]
    remove_tags_after = [dict(name='div', attrs={'class':'news-elm'})]
    #remove_tags_after = [dict(name='div', attrs={'class':'intelliTXT'})]
    
    feeds =  [ ('tomshardware', 'http://www.tomshardware.com/de/feeds/rss2/tom-s-hardware-de,12-1.xml') ] 
    
